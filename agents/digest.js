#!/usr/bin/env node
// ============================================================
//  במגירות — lead & partner digest
//
//  Runs research agents over three tracks, de-duplicates against
//  agents/seen.json, and emails one combined Hebrew (RTL) digest.
//
//  Usage:
//    node agents/digest.js              # full run — all three tracks
//    node agents/digest.js --daily      # opportunities track only (fast, cheap)
//    node agents/digest.js --test       # full run, subject prefixed [TEST]
//    node agents/digest.js --dry-run    # research + render, DO NOT send
//    node agents/digest.js --smoke      # send a tiny email, no research
//
//  Env:
//    ANTHROPIC_API_KEY  required (except --smoke)
//    RESEND_API_KEY     required (except --dry-run)
//    DIGEST_FROM        required — must use a Resend-verified domain
//    DIGEST_TO          default yotamjacob@gmail.com
//
//  Why two API calls per track: the research call uses the web_search server
//  tool, whose results carry citations — and structured outputs
//  (output_config.format) are rejected alongside citations. So research runs
//  free-form, then a second tool-less call structures the findings against a
//  JSON schema. That keeps parsing reliable without fighting the
//  citation/structured-output incompatibility.
//
//  Silence policy: a digest nobody reads is worse than no digest. A --daily
//  run with zero new findings sends NOTHING. The full run always sends, even
//  when empty, so an empty inbox never becomes ambiguous with a broken cron.
// ============================================================

'use strict';

const fs   = require('fs');
const path = require('path');
const Anthropic = require('@anthropic-ai/sdk');
const { partnersPrompt, opportunitiesPrompt, intelPrompt } = require('./prompts');

const ARGS    = process.argv.slice(2);
const IS_TEST = ARGS.includes('--test');
const DRY_RUN = ARGS.includes('--dry-run');
const SMOKE   = ARGS.includes('--smoke');
const DAILY   = ARGS.includes('--daily');

const TO        = process.env.DIGEST_TO || 'yotamjacob@gmail.com';
const FROM      = process.env.DIGEST_FROM;
const SEEN_PATH = path.join(__dirname, 'seen.json');

// Hosts never worth reporting, whatever the model says. Lead-resale directories
// and scraped listing farms look like real businesses in search results but are
// not reachable partners. Add to this list as noise sources are identified.
const BLOCKED_HOSTS = [];

const MODEL = 'claude-opus-5';

const TRACKS = ['partners', 'opportunities', 'intel'];

// ── State ─────────────────────────────────────────────────────

/** Entries are stored as { key, nameKey, name, url }. */
function normaliseEntry(e) {
  if (typeof e === 'string') return { key: e, nameKey: '', name: e, url: '' };
  return { key: e.key || '', nameKey: e.nameKey || '', name: e.name || '', url: e.url || '' };
}

function loadSeen() {
  const empty = () => ({ partners: [], opportunities: [], intel: [], runs: [] });
  try {
    const raw = JSON.parse(fs.readFileSync(SEEN_PATH, 'utf8'));
    const out = empty();
    for (const t of TRACKS) {
      out[t] = (Array.isArray(raw[t]) ? raw[t] : []).map(normaliseEntry);
    }
    out.runs = Array.isArray(raw.runs) ? raw.runs : [];
    return out;
  } catch (e) {
    return empty();
  }
}

function saveSeen(seen) {
  fs.writeFileSync(SEEN_PATH, JSON.stringify(seen, null, 2) + '\n');
}

/**
 * Dedup key. Normalises a URL down to host+path so that tracking params,
 * protocol, www and trailing slashes don't make the same item look new
 * every single run.
 */
function keyOf(item) {
  const url = (item.url || '').trim();
  if (!url) return labelOf(item).toLowerCase().trim();
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, '').toLowerCase();
    const p = u.pathname.replace(/\/+$/, '').toLowerCase();
    return host + p;
  } catch (e) {
    return url.toLowerCase().replace(/\/+$/, '');
  }
}

/** The human label of an item, whichever track it came from. */
function labelOf(item) {
  return String(item.name || item.source || item.topic || '');
}

/**
 * Second de-duplication axis: the identity of the thing, not the link to it.
 * A law firm listed once on its own site and again on a directory page produces
 * two different URL keys for one business — the name catches that.
 */
function nameKeyOf(item) {
  return labelOf(item)
    .toLowerCase()
    .replace(/\b(the|a|an|ltd|limited|inc|group|company)\b/g, '')
    .replace(/(עורך|עורכת|דין|משרד|בע"מ|בעמ|חברת|שירותי)/g, '')
    .replace(/[^a-z0-9֐-׿]/g, '')
    .slice(0, 40);
}

function isBlocked(item) {
  const url = (item.url || '').toLowerCase();
  return BLOCKED_HOSTS.some(h => url.includes(h));
}

// ── Anthropic ─────────────────────────────────────────────────

// Constructed lazily so that requiring this file (for tests, or to reuse the
// renderer) never demands a key — only an actual research run does.
let _client = null;
function getClient() {
  if (_client) return _client;
  // Trim explicitly: a key pasted through a clipboard or `gh secret set` can
  // pick up a trailing newline or stray whitespace, which the API rejects as
  // `invalid x-api-key` — a 401 that looks identical to a genuinely bad key.
  const key = (process.env.ANTHROPIC_API_KEY || '').trim();
  if (!key) throw new Error('ANTHROPIC_API_KEY is not set');
  if (!key.startsWith('sk-ant-')) {
    log(`WARNING: key does not start with "sk-ant-" (starts with "${key.slice(0, 3)}…", length ${key.length}) — this is probably not an Anthropic API key`);
  }
  _client = new Anthropic({ apiKey: key });
  return _client;
}

/**
 * Stage 1 — research with the web_search server tool.
 * Streamed because web search plus adaptive thinking can run long, and a
 * non-streaming call at this max_tokens risks an SDK HTTP timeout.
 */
async function research(prompt, label) {
  log(`[${label}] researching…`);
  const stream = getClient().messages.stream({
    model: MODEL,
    max_tokens: 48000,
    // xhigh: this is agentic search — more tool calls, deeper verification.
    // The extra cost is cents per run and the depth is the whole point.
    output_config: { effort: 'xhigh' },
    tools: [{
      type: 'web_search_20260209',
      name: 'web_search',
      max_uses: 30,
      // No `user_location` — the tool rejects country code IL. Localisation
      // comes from the prompts, which search in Hebrew and name the service
      // area explicitly.
      ...(BLOCKED_HOSTS.length ? { blocked_domains: BLOCKED_HOSTS } : {}),
    }],
    messages: [{ role: 'user', content: prompt }],
  });
  const msg = await stream.finalMessage();

  if (msg.stop_reason === 'refusal') {
    log(`[${label}] refused: ${msg.stop_details?.category || 'unknown'}`);
    return '';
  }
  const text = msg.content.filter(b => b.type === 'text').map(b => b.text).join('\n');
  log(`[${label}] research done (${text.length} chars, ${msg.usage.output_tokens} out-tokens)`);
  return text;
}

/**
 * Stage 2 — structure free-form findings into JSON. No tools, so no citations.
 *
 * Never throws. Research is by far the expensive half of a run, so one track
 * failing to structure must not discard the two that succeeded — it degrades to
 * an empty section and names itself in the log instead.
 */
async function structure(findings, schema, label) {
  try {
    return await structureOnce(findings, schema, label);
  } catch (e) {
    const detail = e && e.status ? `${e.status} ${e.message}` : String(e && e.message || e);
    log(`[${label}] STRUCTURING FAILED: ${detail}`);
    return { summary: `שגיאה בעיבוד ממצאי ${label} — המחקר בוצע אך לא נשמר.`, best_action: '', items: [] };
  }
}

async function structureOnce(findings, schema, label) {
  const empty = { summary: 'לא נמצאו ממצאים חדשים בהרצה הזו.', best_action: '', items: [] };
  if (!findings.trim()) return empty;
  log(`[${label}] structuring… (${findings.length} chars in)`);
  // Read the gate off the schema rather than a per-track flag, so the two can
  // never drift apart. A track whose items carry no `actionable` field is not
  // filtered (see isActionable), and must not be told to talk as if it were.
  const gated = 'actionable' in (schema.properties?.items?.items?.properties || {});
  // Streamed, and with real headroom. Hebrew tokenises far less efficiently
  // than English, and the partners track has produced 14 items in one run —
  // at 16k the JSON was cut mid-string and the whole track was discarded as a
  // parse error. Above ~16k a non-streaming call also risks an SDK timeout.
  const stream = getClient().messages.stream({
    model: MODEL,
    max_tokens: 64000,
    output_config: {
      effort: 'medium',
      format: { type: 'json_schema', schema },
    },
    messages: [{
      role: 'user',
      content:
        'Convert the research notes below into the required JSON structure.\n\n' +
        'Rules:\n' +
        '- Include ONLY items actually present in the notes. Invent nothing.\n' +
        '- Drop anything outside the Haifa–Be\'er Sheva service band.\n' +
        '- Write `summary`, `best_action` and all free-text item fields in ' +
        'HEBREW. Keep URLs, business names and proper nouns as they are.\n' +
        (gated
          ? '- `summary` must be at most two sentences: how many items you ' +
            'examined, how many are actionable, and the single most useful ' +
            'thing among the ACTIONABLE ones. Items marked not-actionable are ' +
            'recorded but never shown to the reader, so never build the ' +
            'summary around one.\n' +
            '- `best_action` is one concrete sentence naming the one thing ' +
            'worth doing first, and must refer to an ACTIONABLE item. Leave ' +
            'it an empty string if nothing is actionable.\n' +
            '- `actionable` is TRUE only for a SPECIFIC, IDENTIFIABLE person ' +
            'or listing that Lior could contact today: it is recent, inside ' +
            'Haifa–Be\'er Sheva, and has a reachable public contact route. ' +
            'Set it FALSE for everything else — including stale posts, ' +
            'login-walled sources, commercial dealers, anything unverified, ' +
            'and anything whose suggested action is to browse a website, ' +
            'monitor a surface, establish a habit, or look into a general ' +
            'observation. "There is a site worth checking manually" is NOT ' +
            'actionable. Be strict: this flag alone decides whether an email ' +
            'is sent, and a false positive trains the reader to ignore the ' +
            'digest.\n'
          // No `actionable` field on this track, so every item it returns is
          // shown. Saying "none of these are actionable" above a page of
          // rendered cards is the contradiction this branch exists to avoid.
          : '- Every item you return WILL be shown to the reader in full. ' +
            'There is no actionability filter on this track, so never write ' +
            'that nothing is actionable or that no action is recommended.\n' +
            '- `summary` must be at most two sentences: how many items you ' +
            'examined, and what the most useful one tells Lior.\n' +
            '- `best_action` is one concrete sentence naming the single thing ' +
            'worth doing first in light of these findings.\n') +
        '\n--- RESEARCH NOTES ---\n' + findings,
    }],
  });

  const msg = await stream.finalMessage();

  if (msg.stop_reason === 'refusal') return empty;

  // Truncation has its own message. It used to surface as an unterminated-string
  // parse error, which reads like a model failure and hides the real cause.
  if (msg.stop_reason === 'max_tokens') {
    log(`[${label}] TRUNCATED at max_tokens (${msg.usage.output_tokens} out-tokens) — findings discarded`);
    return { ...empty, summary: 'הממצאים היו ארוכים מדי לעיבוד בהרצה הזו.' };
  }

  const text = msg.content.filter(b => b.type === 'text').map(b => b.text).join('');
  try {
    return JSON.parse(text);
  } catch (e) {
    log(`[${label}] JSON parse failed (stop_reason=${msg.stop_reason}): ${e.message}`);
    return { ...empty, summary: 'לא הצלחתי לבנות את הממצאים בהרצה הזו.' };
  }
}

// ── Schemas ───────────────────────────────────────────────────

/** Every track shares the same envelope; only `items` differs. */
const envelope = itemProps => ({
  type: 'object',
  additionalProperties: false,
  required: ['summary', 'best_action', 'items'],
  properties: {
    summary:     { type: 'string' },
    best_action: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: Object.keys(itemProps),
        properties: itemProps,
      },
    },
  },
});

const PARTNERS_SCHEMA = envelope({
  name:          { type: 'string' },
  url:           { type: 'string' },
  category:      { type: 'string' },
  location:      { type: 'string' },
  contact:       { type: 'string' },
  why_relevant:  { type: 'string' },
  evidence:      { type: 'string' },
  is_competitor: { type: 'boolean' },
  draft_message: { type: 'string' },
});

const OPPORTUNITIES_SCHEMA = envelope({
  source:          { type: 'string' },
  url:             { type: 'string' },
  date:            { type: 'string' },
  location:        { type: 'string' },
  snippet:         { type: 'string' },
  signal_strength: { type: 'string' },
  suggested_action:{ type: 'string' },
  // Gates whether the daily scan emails at all. A run that surfaces five
  // candidates and rejects all five must stay silent — "new" is not the same
  // as "worth your morning".
  actionable:      { type: 'boolean' },
});

const INTEL_SCHEMA = envelope({
  topic:   { type: 'string' },
  url:     { type: 'string' },
  date:    { type: 'string' },
  finding: { type: 'string' },
  so_what: { type: 'string' },
});

// ── HTML ──────────────────────────────────────────────────────

const GREEN = '#2d4a3e';
const GOLD  = '#a67c2e';
const FONT  = "-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif";

const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

function linkify(url) {
  const u = String(url || '').trim();
  if (!/^https?:\/\//i.test(u)) return esc(u);
  return `<a href="${esc(u)}" dir="ltr" style="color:${GOLD};text-decoration:none">${esc(u.replace(/^https?:\/\//, '').slice(0, 70))}</a>`;
}

function sectionHtml(title, subtitle, data, rows) {
  const items = data.items || [];
  const body = items.length
    ? items.map(rows).join('')
    : `<tr><td style="padding:18px 20px;color:#6b7280;font-size:14px;font-family:${FONT}">
         אין ממצאים חדשים.
       </td></tr>`;

  return `
  <tr><td style="padding:30px 24px 6px">
    <div style="font:700 11px/1 ${FONT};letter-spacing:.1em;color:#9ca3af">${esc(subtitle)}</div>
    <h2 style="margin:8px 0 0;font:700 21px/1.3 ${FONT};color:#111827">${esc(title)}</h2>
    <p style="margin:10px 0 0;font:400 15px/1.55 ${FONT};color:#374151">${esc(data.summary || '')}</p>
    ${data.best_action ? `<p style="margin:12px 0 0;padding:11px 14px;background:#f2f7f4;border-right:3px solid ${GREEN};border-radius:6px 0 0 6px;font:600 14px/1.5 ${FONT};color:${GREEN}">◀ ${esc(data.best_action)}</p>` : ''}
  </td></tr>
  <tr><td style="padding:14px 24px 0">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:0 10px">${body}</table>
  </td></tr>`;
}

const field = (label, value) => value
  ? `<div style="margin-top:7px"><span style="font:700 12px/1.5 ${FONT};color:#6b7280">${esc(label)}</span>
       <span style="font:400 14px/1.55 ${FONT};color:#374151">${esc(value)}</span></div>`
  : '';

const card = inner => `<tr><td style="padding:16px 18px;background:#fff;border:1px solid #e5e7eb;border-radius:9px">${inner}</td></tr>`;

function partnerRow(it) {
  const flag = it.is_competitor
    ? `<span style="font:700 11px ${FONT};color:#b91c1c;background:#fef2f2;padding:2px 7px;border-radius:4px">מתחרה — לא שותף</span>`
    : '';
  return card(`
    <div style="font:700 16px/1.35 ${FONT};color:#111827">${esc(it.name)} ${flag}</div>
    <div style="margin-top:3px;font:400 13px/1.5 ${FONT}">${linkify(it.url)}</div>
    ${field('סוג:', it.category)}
    ${field('אזור:', it.location)}
    ${field('ליצירת קשר:', it.contact)}
    ${field('למה מתאים:', it.why_relevant)}
    ${field('ראיה:', it.evidence)}
    <div style="margin-top:11px;padding:10px 12px;background:#f2f7f4;border-radius:6px">
      <span style="font:700 12px/1.5 ${FONT};color:${GREEN}">טיוטת פנייה — לעבור עליה לפני ששולחים</span><br>
      <span style="font:400 14px/1.6 ${FONT};color:#14532d;white-space:pre-wrap">${esc(it.draft_message)}</span>
    </div>`);
}

function opportunityRow(it) {
  // Non-actionable items never reach here — they are filtered out before
  // rendering (see `display` in main). Anything shown is worth acting on.
  const strong = true;
  return card(`
    <div style="font:700 16px/1.35 ${FONT};color:#111827">${esc(it.source)}
      <span style="font:400 13px;color:#9ca3af">· ${esc(it.date)}</span></div>
    <div style="margin-top:3px;font:400 13px/1.5 ${FONT}">${linkify(it.url)}</div>
    ${field('אזור:', it.location)}
    ${field('מה נכתב:', it.snippet)}
    ${field('עוצמת האות:', it.signal_strength)}
    <div style="margin-top:11px;padding:10px 12px;background:${strong ? '#fffbeb' : '#f9fafb'};border-radius:6px">
      <span style="font:700 12px/1.5 ${FONT};color:${strong ? '#92400e' : '#6b7280'}">פעולה מוצעת</span><br>
      <span style="font:400 14px/1.6 ${FONT};color:${strong ? '#78350f' : '#374151'};white-space:pre-wrap">${esc(it.suggested_action)}</span>
    </div>`);
}

function intelRow(it) {
  return card(`
    <div style="font:700 16px/1.35 ${FONT};color:#111827">${esc(it.topic)}
      ${it.date ? `<span style="font:400 13px;color:#9ca3af">· ${esc(it.date)}</span>` : ''}</div>
    <div style="margin-top:3px;font:400 13px/1.5 ${FONT}">${linkify(it.url)}</div>
    ${field('מה נמצא:', it.finding)}
    <div style="margin-top:11px;padding:10px 12px;background:#f5f3ff;border-radius:6px">
      <span style="font:700 12px/1.5 ${FONT};color:#5b21b6">אז מה עושים עם זה</span><br>
      <span style="font:400 14px/1.6 ${FONT};color:#4c1d95">${esc(it.so_what)}</span>
    </div>`);
}

function renderEmail(dateStr, data, mode) {
  const isDaily = mode === 'daily';
  const sections = isDaily
    ? sectionHtml('הזדמנויות חמות', 'סריקה יומית', data.opportunities, opportunityRow)
    : sectionHtml('שותפים פוטנציאליים', 'מסלול א', data.partners, partnerRow)
      + sectionHtml('הזדמנויות חמות', 'מסלול ב', data.opportunities, opportunityRow)
      + sectionHtml('מודיעין שוק', 'מסלול ג', data.intel, intelRow);

  return `<!doctype html><html dir="rtl" lang="he"><body style="margin:0;padding:0;background:#f3f4f6" dir="rtl">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:22px 12px" dir="rtl">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#fff;border-radius:13px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.09)">

  <tr><td style="padding:26px 24px;background:${GREEN}">
    <div style="font:700 20px/1.3 ${FONT};color:#fff">במגירות · ${isDaily ? 'סריקה יומית' : 'דוח שבועי'}</div>
    <div style="margin-top:5px;font:400 14px/1.4 ${FONT};color:${GOLD}">${esc(dateStr)} · חיפה–באר שבע</div>
  </td></tr>

  ${sections}

  <tr><td style="padding:24px;border-top:1px solid #e5e7eb">
    <p style="margin:0;font:400 12px/1.6 ${FONT};color:#9ca3af">
      מחקר בלבד — שום דבר לא נשלח ולא פורסם לאף אחד. כל פנייה וכל טיוטה
      מיועדות לבדיקה ולשליחה ידנית.<br>
      קבוצות פייסבוק סגורות ומקורות שדורשים התחברות אינם נסרקים.
      פריטים שדווחו בהרצות קודמות מסוננים דרך <code>agents/seen.json</code>.
    </p>
  </td></tr>

</table></td></tr></table></body></html>`;
}

// ── Delivery ──────────────────────────────────────────────────

async function sendEmail(subject, html) {
  const key = process.env.RESEND_API_KEY;
  if (!key)  throw new Error('RESEND_API_KEY is not set');
  if (!FROM) throw new Error('DIGEST_FROM is not set (must be a Resend-verified sending domain)');

  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ from: FROM, to: [TO], subject, html }),
  });
  const body = await res.text();
  if (!res.ok) throw new Error(`Resend ${res.status}: ${body}`);
  log(`email sent → ${TO} (${JSON.parse(body).id})`);
}

function log(msg) { console.log(`[digest] ${msg}`); }

// ── Main ──────────────────────────────────────────────────────

const emptySection = note => ({ summary: note, best_action: '', items: [] });

async function main() {
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10);
  const mode = DAILY ? 'daily' : 'full';

  if (SMOKE) {
    const note = 'בדיקת מערכת — לא בוצע מחקר.';
    await sendEmail(
      `[SMOKE] במגירות — בדיקת מערכת ${dateStr}`,
      renderEmail(dateStr, {
        partners:      emptySection(note),
        opportunities: emptySection(note),
        intel:         emptySection(note),
      }, 'full'),
    );
    return;
  }

  const seen = loadSeen();
  log(`mode: ${mode} · seen: ${TRACKS.map(t => `${t}=${seen[t].length}`).join(', ')}`);

  // Which tracks run this time. The daily run is deliberately narrow: the
  // partner and intel tracks produce nothing new day-to-day and would just
  // burn tokens.
  const active = DAILY ? ['opportunities'] : TRACKS;

  const spec = {
    partners:      { prompt: partnersPrompt,      schema: PARTNERS_SCHEMA },
    opportunities: { prompt: opportunitiesPrompt, schema: OPPORTUNITIES_SCHEMA },
    intel:         { prompt: intelPrompt,         schema: INTEL_SCHEMA },
  };

  // Tracks are independent — research them concurrently.
  const raw = await Promise.all(
    active.map(t => research(spec[t].prompt(seen[t]), t)),
  );
  const structured = await Promise.all(
    active.map((t, i) => structure(raw[i], spec[t].schema, t)),
  );

  // Enforcement layer 2 + dedup.
  const filterNew = (data, seenEntries, label) => {
    const before = (data.items || []).length;
    const urlKeys  = new Set(seenEntries.map(e => e.key).filter(Boolean));
    const nameKeys = new Set(seenEntries.map(e => e.nameKey).filter(Boolean));
    // Also guard against the same item appearing twice within one run.
    const thisRun = new Set();
    const kept = [];
    for (const it of data.items || []) {
      if (isBlocked(it)) { log(`  [${label}] dropped (blocked source): ${labelOf(it)}`); continue; }
      const k  = keyOf(it);
      const nk = nameKeyOf(it);
      if (!k && !nk) continue;
      if (k && urlKeys.has(k))               { log(`  [${label}] skip (seen url): ${labelOf(it)}`); continue; }
      if (nk && nameKeys.has(nk))            { log(`  [${label}] skip (seen name): ${labelOf(it)}`); continue; }
      if (thisRun.has(k) || thisRun.has(nk)) { log(`  [${label}] skip (dupe in run): ${labelOf(it)}`); continue; }
      if (k) thisRun.add(k);
      if (nk) thisRun.add(nk);
      kept.push(it);
    }
    if (before !== kept.length) log(`  [${label}] filtered ${before} → ${kept.length}`);
    return { ...data, items: kept };
  };

  const skipped = emptySection('לא נסרק בהרצה הזו.');
  const data = { partners: skipped, opportunities: skipped, intel: skipped };
  active.forEach((t, i) => { data[t] = filterNew(structured[i], seen[t], t); });

  // Tracks without an `actionable` field are actionable by definition: a
  // partner prospect or a market finding is always something to act on.
  const isActionable = it => it.actionable !== false;

  const total      = active.reduce((n, t) => n + data[t].items.length, 0);
  const actionable = active.reduce((n, t) => n + data[t].items.filter(isActionable).length, 0);
  log(`new this run: ${active.map(t => `${t}=${data[t].items.length}`).join(', ')} · actionable=${actionable}`);

  // What gets EMAILED is actionable items only. Checked-and-rejected findings
  // are noise in an inbox — but they are still recorded below, so tomorrow's
  // scan doesn't re-research the same dead listings. The section summary still
  // states how many were examined, so a quiet section reads as "we looked"
  // rather than "nothing ran".
  const display = Object.fromEntries(
    Object.entries(data).map(([t, sec]) => [t, { ...sec, items: sec.items.filter(isActionable) }]),
  );

  const html = renderEmail(dateStr, display, mode);
  const label = mode === 'daily' ? 'סריקה יומית' : 'דוח שבועי';
  const subject = `${IS_TEST ? '[TEST] ' : ''}במגירות · ${label} — ${dateStr}${actionable ? ` (${actionable} חדשים)` : ''}`;

  if (DRY_RUN) {
    const out = path.join(__dirname, 'preview.html');
    fs.writeFileSync(out, html);
    log(`dry run — wrote ${out}, nothing sent`);
    return;
  }

  // Recording is the same on both paths below, so define it once. Items are
  // only ever recorded after the send decision has been honoured, so a
  // delivery failure never silently swallows a run's findings.
  const record = it => ({
    key: keyOf(it), nameKey: nameKeyOf(it),
    name: labelOf(it), url: it.url || '',
  });
  const commit = sent => {
    for (const t of active) seen[t].push(...data[t].items.map(record));
    seen.runs.push({
      at: now.toISOString(), mode, total, actionable, sent,
      ...Object.fromEntries(active.map(t => [t, data[t].items.length])),
    });
    if (seen.runs.length > 100) seen.runs = seen.runs.slice(-100);
    saveSeen(seen);
    log('seen.json updated');
  };

  // Silence policy. The gate is ACTIONABLE items, not new ones: a scan that
  // surfaces five candidates and correctly rejects all five has found nothing
  // worth your morning, and sending it anyway is how a digest gets ignored.
  // The weekly run always sends, so a quiet week is never confused with a
  // broken cron.
  //
  // Rejected items are still recorded — otherwise the same dead listings would
  // resurface and be re-researched every single day.
  if (actionable === 0 && mode === 'daily' && !IS_TEST) {
    log(`nothing actionable on the daily scan (${total} examined) — not sending`);
    commit(false);
    return;
  }

  await sendEmail(subject, html);
  commit(true);
}

if (require.main === module) {
  main().catch(err => {
    console.error('[digest] FAILED:', err.message);
    process.exit(1);
  });
}

// Exported so the renderer and the de-duplication keys can be exercised
// without making any API call.
module.exports = { renderEmail, keyOf, nameKeyOf, labelOf, normaliseEntry };
