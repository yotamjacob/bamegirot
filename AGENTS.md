# Repository guide

## Project

`bamegirot.com` is a production Hebrew landing page for Lior's antique,
estate-content, and vintage-item appraisal/sales service. It is intentionally
plain HTML/CSS/JavaScript: there is no framework, package manager, build step,
or server-side code.

The primary product goal is qualified WhatsApp contact. Preserve SEO,
accessibility, mobile behavior, and Google Ads conversion tracking when making
changes.

## Source map

- `index.html` contains all page markup, CSS, inline JavaScript, SEO metadata,
  and JSON-LD.
- `images/cover.webp` is the optimized hero image. `images/cover.jpg` is kept
  for Open Graph/schema consumers. `images/item-*.webp` are the gallery.
  `images/portrait.webp` is the available portrait asset.
- Gallery items also have responsive variants `item-NN-{400,600,800}.webp`
  referenced from `srcset`. Widths within 90% of the original are skipped, so
  not every item has all three. Replacing a gallery image means regenerating
  its variants and updating both `srcset` and the `width`/`height` attributes.
  `check_site.py` does not parse `srcset`; verify those paths by hand.
- `favicon.svg`, `robots.txt`, `sitemap.xml`, and both `google*.html` files are
  production assets. Do not rename or remove the Google verification files.
- `TODO.md` tracks business/launch work, not code architecture.
- `scripts/check_site.py` is the fast static validation command.

## Production facts

Treat these as fixed unless the user explicitly changes them:

- Brand: `במגירות`; owner/voice: Lior Buchstab (`ליאור בוכשטב`),
  first-person feminine Hebrew.
- Main service area: `מתל אביב ועד חיפה` (Tel Aviv to Haifa).
- Canonical domain: `https://www.bamegirot.com/`.
- WhatsApp: `972523321045`.
- Google Ads account tag: `AW-10933411346`; the conversion label is in the
  click handler near the end of `index.html`.
- GA4 measurement ID: `G-N75RDS0BKM`, configured through the same `gtag.js`
  load as the Ads tag. Do not add a second gtag.js script tag.
- Document language/direction: `<html lang="he" dir="rtl">`.

## Editing rules

- Preserve the warm antique visual system. Change shared colors, type, spacing,
  radii, or widths through the CSS custom properties in `:root`.
- Keep copy empathetic, direct, and non-pressuring. Do not invent claims,
  testimonials, prices, experience, or service terms.
- Keep duplicated facts synchronized:
  - visible FAQ questions/answers and `FAQPage` JSON-LD;
  - domain in canonical, Open Graph, schema, sitemap, and robots;
  - phone/message across every `wa.me` link and schema;
  - business description across metadata, schema, and visible copy when the
    underlying claim changes.
- Use optimized WebP for visible raster images. Keep useful Hebrew `alt` text
  and `loading="lazy"` below the fold; do not lazy-load the hero.
- Links opened with `target="_blank"` must keep `rel="noopener"`.
- Avoid new dependencies or a framework for a small change. Ask before changing
  the zero-build architecture.
- Never deploy, modify DNS, change analytics IDs, or alter live ad tracking
  unless explicitly requested.
- Keep one self-referencing canonical, one metadata set, and one JSON-LD
  `@graph`. Do not describe the business as directly buying contents.

## Fast workflow

1. Locate the relevant section with `rg -n '<term>' index.html`; avoid reading
   the entire 1,400-line file when a targeted section is enough.
2. Make the smallest coherent edit.
3. Run:

   ```sh
   python3 scripts/check_site.py
   git diff --check
   ```

4. For visual or interaction changes, serve the repository and check both a
   narrow mobile viewport and desktop:

   ```sh
   python3 -m http.server 8000
   ```

   Then open `http://localhost:8000/`. Verify the FAQ accordion, header scroll
   behavior, back-to-top control, WhatsApp targets, RTL layout, and image crops
   relevant to the change.

## Review priorities

Flag broken WhatsApp conversion paths, inaccurate business claims, SEO/schema
drift, missing local assets, JavaScript that prevents interactions/tracking,
mobile overflow, and accessibility regressions. Pure formatting preferences
are lower priority.
