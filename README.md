# במגירות

A production, single-page Hebrew landing site for Lior's antique, estate
contents, and vintage-item appraisal and sales service:
[www.bamegirot.com](https://www.bamegirot.com/).

The site is optimized for WhatsApp enquiries and Google search/ads. It uses
plain HTML, CSS, and JavaScript with no dependencies or build step.

## Repository

- `index.html` — all page markup, styles, scripts, SEO metadata, and JSON-LD.
- `images/` — optimized WebP page images plus the JPEG social-sharing image.
- `favicon.svg` — site icon.
- `robots.txt`, `sitemap.xml`, `google*.html` — search-engine assets and
  ownership verification.
- `vercel.json` — canonical-host redirects, trailing-slash policy, and response
  headers for the Vercel deployment.
- `TODO.md` — operational and content follow-ups.
- `AGENTS.md` — durable instructions for Codex and other coding agents.
- `scripts/check_site.py` — fast static checks for common production mistakes.

## Run locally

From the repository root:

```sh
python3 -m http.server 8000
```

Open [http://localhost:8000/](http://localhost:8000/). Google Fonts and Ads
scripts require an internet connection; the page itself and its images are
local.

## Validate changes

```sh
python3 scripts/check_site.py
git diff --check
```

The checker uses Python's standard library and, when Node.js is available,
also checks the syntax of inline JavaScript. It verifies local assets, fragment
links, image alt text, structured data, FAQ/schema parity, production URLs,
WhatsApp consistency, heading/landmark structure, image dimensions/loading,
crawl directives, sitemap contents, and Vercel routing configuration.

For layout or interaction changes, also inspect desktop and mobile widths.
Exercise the FAQ accordion, scroll header, back-to-top button, and WhatsApp
links.

## Editing notes

- The document is Hebrew and RTL (`lang="he"`, `dir="rtl"`).
- Shared design tokens are CSS custom properties at the top of the `<style>`
  block in `index.html`.
- Visible raster images use WebP. `images/cover.jpg` remains in the repository
  because Open Graph and schema metadata reference it.
- FAQ content exists twice: visibly on the page and in `FAQPage` JSON-LD.
- The production domain and phone number also appear in several metadata,
  schema, and CTA locations. Keep every copy synchronized.
- Preserve Lior's first-person feminine voice and do not invent business claims
  or testimonials.

See `AGENTS.md` for the complete editing and review contract.

## Deployment

The GitHub repository is connected to the Vercel project `mom-antiques`.
Changes pushed to the configured production branch are deployed by Vercel.
Domain and launch follow-ups are tracked in `TODO.md`.

Do not run a production deployment or change DNS/analytics identifiers as part
of an ordinary content or design edit unless that action was explicitly
requested.
