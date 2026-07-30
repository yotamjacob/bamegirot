# CLAUDE.md

**Read [AGENTS.md](AGENTS.md) first.** It is the authoritative editing and review
contract for this repo (source map, production facts, copy rules, schema/FAQ
parity, review priorities). Everything here is Claude-specific operational
detail that is *not* in AGENTS.md — it does not replace it.

## Orientation in one pass

Zero-build static site. No package manager, no framework, no server code.
Everything visible lives in one file.

```
index.html   1,479 lines — ALL markup, CSS, JS, meta, JSON-LD
  1-200      head: meta, OG/Twitter, JSON-LD @graph, gtag
  202-978    <style> (design tokens in :root at the top)
  987-1400   header, hero, #how-it-works, #sold-items, #about,
             #faq, #whatsapp-cta, #expertise
  1401-1479  footer + inline JS (accordion, scroll header,
             back-to-top, WhatsApp conversion click handler)
images/      cover.webp (hero) · cover.jpg (OG/schema only) ·
             item-01..21.webp (gallery) · portrait.webp (unused)
scripts/check_site.py   the validator — run it, don't hand-verify
```

Never read `index.html` whole. Locate first:
`rg -n '<term>' index.html`, then read that range only.

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

## Repo state on takeover (2026-07-30)

A large uncommitted SEO/content overhaul from the previous agent is sitting in
the working tree and is **not committed and not deployed**. The live site still
serves the old `71851da` build.

- `index.html` — new title/description/OG/Twitter set, JSON-LD rewritten from a
  flat `LocalBusiness` into a connected `@graph` (6 entities, 7 FAQs)
- `robots.txt` — per-bot rules incl. `OAI-SearchBot`, `PerplexityBot`
- `sitemap.xml` — `lastmod` dropped
- `vercel.json`, `AGENTS.md`, `scripts/check_site.py` — new, untracked

`check_site.py` passes on all of it. It needs the user's review of the Hebrew
copy before it ships, since it changes the public positioning.
