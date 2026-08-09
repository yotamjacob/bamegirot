# CLAUDE.md

**Read [AGENTS.md](AGENTS.md) first.** It is the authoritative editing and review
contract for this repo (source map, production facts, copy rules, schema/FAQ
parity, review priorities). Everything here is Claude-specific operational
detail that is *not* in AGENTS.md — it does not replace it.

## Orientation in one pass

Zero-build static site. No package manager, no framework, no server code.
Everything visible lives in one file.

```
index.html   ~1,560 lines — the homepage: ALL its markup, CSS, JS, meta, JSON-LD
  1-210      head: meta, OG/Twitter, JSON-LD @graph, gtag
  211-992    <style> (design tokens in :root at the top)
  995-1450   header, hero, #how-it-works, #sold-items, #about,
             #faq, #whatsapp-cta, #expertise
  1450-end   footer (incl. both guide link groups) + inline JS
             (accordion, scroll header, back-to-top, WhatsApp
             conversion click handler)
guides/      the hub + ten guide pages — see "The guides" below
images/      cover.webp (hero) · cover.jpg (OG/schema only) ·
             item-01..21.webp (gallery) · portrait.webp (unused)
scripts/check_site.py   the validator — run it, don't hand-verify
```

Line numbers drift with every edit — treat them as a rough map, not an index.
Never read `index.html` whole. Locate first: `rg -n '<term>' index.html`, then
read that range only.

## Every change ends with

```sh
python3 scripts/check_site.py   # must print "site checks passed"
git diff --check
```

The checker covers local assets, fragment links, alt text, JSON-LD validity,
FAQ↔schema parity, production URLs, WhatsApp consistency, headings/landmarks,
image dimensions/loading, robots, sitemap, and vercel.json routing. If it
passes, the mechanical risks are already covered — spend review effort on copy
accuracy and layout instead.

Visual/interaction changes only: `python3 -m http.server 8000`, then check a
narrow mobile viewport *and* desktop. Exercise the FAQ accordion, scroll
header, back-to-top, and WhatsApp links.

## The leads agent (`agents/`)

Separate from the site. A research agent that emails a Hebrew RTL digest of
referral prospects and live opportunities in the Haifa–Be'er Sheva band.

```
agents/digest.js    tracks, dedup, rendering, Resend delivery
agents/prompts.js   the three research prompts — tune wording here
agents/seen.json    dedup state, COMMITTED (CI pushes it back)
.github/workflows/leads-digest.yml   Sunday = full run, Mon-Sat = daily scan
```

The daily scan emails only when at least one opportunity comes back with
`actionable: true` — a scan that surfaces five candidates and rejects all five
has found nothing worth the reader's morning. Rejected items are still written
to `seen.json` so they aren't re-researched tomorrow. The Sunday run always
sends, so a quiet week never looks like a dead cron.

```sh
cd agents && npm install
node agents/digest.js --dry-run    # research + render to agents/preview.html
node agents/digest.js --smoke      # send a stub email, no research
```

Two things that are load-bearing and easy to break:

- **`package.json` lives in `agents/`, never at the repo root.** A root
  `package.json` makes Vercel stop treating this as a zero-build static site.
  `.vercelignore` excludes `agents/`, `scripts/`, `.github/` and the `.md`
  files from the deployment for the same reason.
- **Lior appraises estates and manages the sale — she does not buy contents.**
  `prompts.js` says so explicitly. Any copy the agent drafts must respect it.

The prompts forbid four things absolutely: touching anything behind a login
(Facebook groups included), contacting anyone off an obituary or shiva notice,
sending anything automatically, and **any lawyer, law firm or notary as a
referral target** (standing decision, 2026-08-05 — they were the original
priority-1 category and were removed on request). Every draft is for a human to
review. Keep all four rules if you rewrite the prompts.

## Deployment

```sh
~/.npm-global/bin/vercel --prod --yes    # run from repo root
```

The user's standing preference is to deploy after an edit session. AGENTS.md
says never deploy unless explicitly requested. **Resolution: ask once at the
end of a session that changed production files, then deploy.** Do not deploy
mid-task, and never touch DNS, the Google Ads tag (`AW-10933411346`), or the
conversion label as part of an ordinary edit.

Vercel project: `mom-antiques` (`.vercel/project.json`). The GitHub repo is
also connected, so a push to `main` deploys too — avoid doing both for one
change.

## Git

Remote is pinned to the **personal** account:
`https://yotamjacob@github.com/yotamjacob/bamegirot.git`

Keep the username in the URL. The macOS keychain otherwise resolves HTTPS
GitHub to the work account (`yotam-jacob`), which must not touch this repo.

## The guides

Eleven pages hang off `/guides/`, all committed and live.

```
guides/index.html          the hub — two sections, and the ItemList that
                           must stay in step with what's actually there
guides/<slug>/index.html   five process guides (what to do, in what order)
                           + five per-item-type pages (<thing>-value)
```

Each page is standalone: its own copy of the design tokens, the WhatsApp
button, and the gtag conversion handler. There is no shared stylesheet — that
is the cost of staying zero-build, so a token change means editing every file.

Adding a guide means four edits, and `check_site.py` fails if you miss the
third: the new directory, a card on the hub, a `sitemap.xml` entry, and the
hub's `ItemList` (`numberOfItems` plus a `ListItem`).

**Item-type pages must be illustrated with real photographs from estates Lior
handled** — that is the whole reason they beat a buyer's page on the same
query. `images/item-01..21.webp` is the entire available library. Judaica,
silver, and signed paintings have no photography, which is why those pages do
not exist despite the site claiming those categories; build them when Lior
supplies photos, not before.

Copy is shipped without Lior's review (user's standing decision, 2026-08-09).
Keep it accurate to the positioning: she appraises and accompanies the sale,
and never buys the contents.
