# במגירות — TODO

## Before launch

- [ ] Review the "קצת עליי" paragraph — confirm Lior is happy with the wording

## Content decisions from repository audit

- [ ] Confirm the "קצת עליי" image. The page currently reuses
  `images/cover.webp`; `images/portrait.webp` exists but contains a three-person
  photo and is not referenced.

## Connect bamegirot.com domain (Wix → Vercel)

**Step 1 — Add domain in Vercel**
- [ ] Go to vercel.com → your project (mom-antiques) → Settings → Domains
- [ ] Add `bamegirot.com` → Vercel will show you the DNS records to copy

**Step 2 — Add DNS records in Wix**
- [ ] Log in to wix.com → Domains → Manage next to bamegirot.com
- [ ] Go to Advanced → DNS Records
- [ ] Add an **A record**: Host = `@` · Value = `76.76.21.21` (Vercel's IP)
- [ ] Add a **CNAME record**: Host = `www` · Value = `cname.vercel-dns.com`
- [ ] Delete any existing A record pointing to Wix (if one exists for `@`)
- [ ] Save

**Step 3 — Wait & verify**
- [ ] Wait up to 48 hours for DNS to propagate (usually under 1 hour)
- [ ] Visit https://bamegirot.com — should load the site with a green padlock
- [ ] Visit https://www.bamegirot.com — should redirect to the same site

**Step 4 — Cleanup**
- [ ] Update the OG image meta tag in index.html if it doesn't already point to bamegirot.com (it already does — just verify it loads)
- [ ] Run `~/.npm-global/bin/vercel --prod --yes` to redeploy with the live domain active

## Done

- [x] Business name → במגירות
- [x] WhatsApp number → 972523321045
- [x] Years of experience → 5+
- [x] Families helped → עשרות+
- [x] Domain → https://www.bamegirot.com/
- [x] Hero cover image — full-bleed with text overlay
- [x] 3 real testimonials (מיכל, ליאת, יעל)
- [x] Portrait asset added → images/portrait.webp (not currently used; see audit item)
- [x] SEO and visible positioning aligned: במגירות evaluates and supports sales;
      it does not directly purchase the contents
- [x] Remaining unverified "without cost" claims removed; "without obligation" retained
- [x] 21 item photos → sold items gallery section
- [x] Removed all "free evaluation" / "חינם" references
- [x] Removed all silver / "כסף ישן" references
- [x] Voice changed to first-person (ליאור) throughout
- [x] Mobile optimized — floating WhatsApp button, responsive gallery, full-width CTAs
