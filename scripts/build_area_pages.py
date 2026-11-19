#!/usr/bin/env python3
"""Generate the service-area pages: areas/index.html and areas/<city>/index.html.

The city pages are the one place on the site that is generated rather than
hand-edited, because ten pages that share a layout drift apart quickly when
edited by hand. Edit the copy in CITIES below, then run:

    python3 scripts/build_area_pages.py
    python3 scripts/build_sitemap.py
    python3 scripts/check_site.py

Dates are kept honest without --touch: a page whose generated HTML is
unchanged keeps its dateModified; a page whose copy changed gets today's date.

Copy rules (see AGENTS.md): Lior appraises and accompanies the sale, she never
buys the contents. Local paragraphs describe the town and its housing in
general terms. They must not claim specific jobs Lior did there. The only
first-hand local proof is a real testimonial, and only Ramat Hasharon and
Hadera have one.

``shell()`` is also used to write the about page, the English homepage and new
guides, so they share one head, footer and tracking snippet.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://www.bamegirot.com/"
WA_NUMBER = "972523321045"
sys.path.insert(0, str(ROOT / "scripts"))
from build_sitemap import visible_label  # noqa: E402

AUTHOR = {
    "@type": "Person",
    "@id": f"{BASE}#lior-buchstab",
    "name": "ליאור בוכשטב",
    "url": f"{BASE}about/",
}
PUBLISHER = {
    "@type": "Organization",
    "@id": f"{BASE}#business",
    "name": "במגירות",
    "url": BASE,
    "logo": {"@type": "ImageObject", "url": f"{BASE}images/logo.png", "width": 512, "height": 512},
}

WA_ICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'
    '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.297-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
)

CSS = """
    :root {
      --color-bg:           #f5efe6;
      --color-bg-alt:       #ebe1ce;
      --color-surface:      #fbf7f0;
      --color-text:         #1a1612;
      --color-text-muted:   #6b5f52;
      --color-primary:      #2d4a3e;
      --color-primary-dark: #1e332b;
      --color-accent:       #a67c2e;
      --color-border:       #d4c5ae;
      --color-whatsapp:     #25D366;
      --color-whatsapp-dark:#1da851;
      --font-display: 'Suez One', 'Frank Ruhl Libre', Georgia, 'Times New Roman', serif;
      --font-body:    'Heebo', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      --radius-md: 12px;
      --radius-lg: 20px;
      --shadow-md: 0 4px 12px rgba(26, 22, 18, 0.08), 0 2px 4px rgba(26, 22, 18, 0.04);
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: var(--font-body);
      background-color: var(--color-bg);
      color: var(--color-text);
      line-height: 1.75;
      font-size: 17px;
      -webkit-font-smoothing: antialiased;
    }
    a { color: var(--color-primary); }
    .top-strip { background: var(--color-primary-dark); padding: 0.7rem 1.25rem; }
    .top-strip a { color: var(--color-bg); text-decoration: none; font-weight: 500; font-size: 0.95rem; }
    .top-strip a:hover { text-decoration: underline; }
    .top-strip-sep { color: var(--color-bg); opacity: 0.5; margin: 0 0.5rem; }
    .wrap { max-width: 720px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }
    h1 {
      font-family: var(--font-display);
      font-size: clamp(1.7rem, 5vw, 2.4rem);
      line-height: 1.3;
      color: var(--color-primary-dark);
      margin-bottom: 0.75rem;
    }
    .byline {
      color: var(--color-text-muted);
      font-size: 0.95rem;
      margin-bottom: 2rem;
      padding-bottom: 1.25rem;
      border-bottom: 1px solid var(--color-border);
    }
    .byline a { color: inherit; }
    article h2 {
      font-family: var(--font-display);
      font-size: clamp(1.25rem, 3.5vw, 1.55rem);
      color: var(--color-primary);
      margin: 2.25rem 0 0.75rem;
    }
    article h3 { font-size: 1.08rem; margin: 1.25rem 0 0.35rem; color: var(--color-primary-dark); }
    article p { margin-bottom: 1rem; }
    article ul, article ol { margin-block: 0 1rem; margin-inline-start: 1.4rem; }
    article li { margin-bottom: 0.5rem; }
    .callout {
      background: var(--color-bg-alt);
      border-inline-start: 4px solid var(--color-accent);
      border-radius: var(--radius-md);
      padding: 1.1rem 1.3rem;
      margin: 1.5rem 0;
    }
    .callout p:last-child { margin-bottom: 0; }
    .photo { margin: 1.75rem 0; }
    .photo img { display: block; width: 100%; height: auto; max-height: 460px; object-fit: cover; border-radius: var(--radius-md); }
    .photo figcaption { color: var(--color-text-muted); font-size: 0.9rem; margin-top: 0.4rem; }
    .quote {
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 1.2rem 1.4rem;
      margin: 1rem 0 1.5rem;
    }
    .quote p { margin-bottom: 0.5rem; }
    .quote cite { color: var(--color-text-muted); font-style: normal; font-size: 0.95rem; }
    .card-list { list-style: none; margin: 1.25rem 0 0 !important; padding: 0; display: grid; gap: 0.9rem; }
    @media (min-width: 640px) { .card-list { grid-template-columns: repeat(2, 1fr); } }
    .card-list li { margin: 0; }
    .card-list a {
      display: block;
      height: 100%;
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-md);
      padding: 1rem 1.2rem;
      text-decoration: none;
      color: var(--color-text);
      transition: box-shadow 0.2s, border-color 0.2s;
    }
    .card-list a:hover, .card-list a:focus-visible { box-shadow: var(--shadow-md); border-color: var(--color-accent); }
    .card-list strong { display: block; font-family: var(--font-display); font-weight: 400; color: var(--color-primary); font-size: 1.15rem; }
    .card-list span { color: var(--color-text-muted); font-size: 0.95rem; }
    .next-reads { margin: 2.25rem 0 0; }
    .next-reads ul { list-style: none; margin: 0; padding: 0; }
    .next-reads li { margin-bottom: 0.5rem; }
    .cta-box {
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      box-shadow: var(--shadow-md);
      padding: 2rem 1.5rem;
      margin-top: 3rem;
      text-align: center;
    }
    .cta-box h2 { font-family: var(--font-display); color: var(--color-primary-dark); margin: 0 0 0.6rem; font-size: 1.4rem; }
    .cta-box p { color: var(--color-text-muted); margin-bottom: 1.25rem; }
    .btn-whatsapp {
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      background: var(--color-whatsapp);
      color: #fff;
      font-weight: 700;
      font-size: 1.05rem;
      text-decoration: none;
      padding: 0.9rem 1.8rem;
      border-radius: 999px;
      transition: background 0.2s;
    }
    .btn-whatsapp:hover { background: var(--color-whatsapp-dark); }
    .btn-whatsapp svg { width: 22px; height: 22px; }
    .site-footer { background: var(--color-primary-dark); color: var(--color-bg); padding: 2.5rem 1.25rem; font-size: 0.95rem; }
    .site-footer .wrap { padding: 0; }
    .site-footer p { margin-bottom: 0.6rem; opacity: 0.9; }
    .site-footer a { color: var(--color-bg); }
    .footer-copy { margin-top: 1.25rem; opacity: 0.7; font-size: 0.85rem; }
"""

GTAG = """  <!-- Google Ads conversion tracking + GA4 analytics (one gtag.js for both) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=AW-10933411346"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'AW-10933411346');
    gtag('config', 'G-N75RDS0BKM');
  </script>"""

TRACKING = """  <script>
    // Google Ads — fire lead conversions. 'beacon' transport survives the
    // page unloading when the WhatsApp / phone app takes over on mobile.
    const trackLead = sendTo => () => {
      gtag('event', 'conversion', {
        'send_to': sendTo,
        'transport_type': 'beacon'
      });
    };
    document.querySelectorAll('a[href*="wa.me"]').forEach(link => {
      link.addEventListener('click', trackLead('AW-10933411346/F_bFCM_o-J4cEJK8ut0o'));
    });
    document.querySelectorAll('a[href^="tel:"]').forEach(link => {
      link.addEventListener('click', trackLead('AW-10933411346/U4JGCLrCm9ocEJK8ut0o'));
    });
  </script>"""

FOOTER_HE = """  <footer class="site-footer">
    <div class="wrap">
      <p><strong>במגירות</strong> מעריכה תכולת דירה ועזבונות ומלווה את מכירת הפריטים.</p>
      <p><a href="/areas/">אזור שירות: מתל אביב ועד חיפה</a> · <a href="tel:+972523321045">טלפון: <bdi>052-332-1045</bdi></a> · <a href="/about/">קצת עליי</a> · <a href="https://www.bamegirot.com/">www.bamegirot.com</a></p>
      <div class="footer-copy">ליאור בוכשטב · במגירות · &copy; 2026</div>
    </div>
  </footer>"""


def wa_link(text: str) -> str:
    return f"https://wa.me/{WA_NUMBER}?text={urllib.parse.quote(text)}"


def cta(title: str, body: str, message: str, button: str = "שלחו לי תמונות בוואטסאפ") -> str:
    return f"""      <div class="cta-box">
        <h2>{title}</h2>
        <p>{body}</p>
        <a class="btn-whatsapp" href="{wa_link(message)}">
          {WA_ICON}
          {button}
        </a>
      </div>"""


def faq_entity(url: str, pairs: list[tuple[str, str]]) -> dict:
    return {
        "@type": "FAQPage",
        "@id": f"{url}#faq",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}}
            for q, a in pairs
        ],
    }


def faq_html(pairs: list[tuple[str, str]]) -> str:
    return "\n".join(f"      <h3>{q}</h3>\n      <p>{a}</p>" for q, a in pairs)


def breadcrumbs(url: str, trail: list[tuple[str, str | None]]) -> dict:
    items = []
    for position, (name, item) in enumerate(trail, 1):
        entry = {"@type": "ListItem", "position": position, "name": name}
        if item:
            entry["item"] = item
        items.append(entry)
    return {"@type": "BreadcrumbList", "@id": f"{url}#breadcrumbs", "itemListElement": items}


def shell(
    *,
    url: str,
    title: str,
    description: str,
    og_title: str,
    og_type: str,
    graph: list[dict],
    nav: str,
    body: str,
    lang: str = "he",
    image: str = f"{BASE}images/cover.jpg",
    image_size: tuple[int, int] = (1023, 600),
    image_alt: str = "איור של שיחה על הערכת תכולת דירה ועזבון",
    hreflang: dict[str, str] | None = None,
    footer: str = FOOTER_HE,
    dates: tuple[str, str] | None = None,
) -> str:
    rtl = lang == "he"
    esc = lambda value: html.escape(value, quote=True)  # noqa: E731
    ld = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2)
    ld = "\n".join("  " + line for line in ld.splitlines())
    alternates = "".join(
        f'\n  <link rel="alternate" hreflang="{code}" href="{href}" />' for code, href in (hreflang or {}).items()
    )
    article_meta = ""
    if og_type == "article" and dates:
        article_meta = (
            f'\n  <meta property="article:published_time" content="{dates[0]}" />'
            f'\n  <meta property="article:modified_time" content="{dates[1]}" />'
        )
    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{'rtl' if rtl else 'ltr'}">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <link rel="canonical" href="{url}" />{alternates}
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />

  <meta property="og:type" content="{og_type}" />
  <meta property="og:locale" content="{'he_IL' if rtl else 'en_US'}" />
  <meta property="og:site_name" content="{'במגירות' if rtl else 'Bamegirot'}" />
  <meta property="og:title" content="{esc(og_title)}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{image}" />
  <meta property="og:image:width" content="{image_size[0]}" />
  <meta property="og:image:height" content="{image_size[1]}" />
  <meta property="og:image:alt" content="{esc(image_alt)}" />{article_meta}
  <meta name="twitter:card" content="summary_large_image" />

  <script type="application/ld+json">
{ld}
  </script>

  <!-- Fonts: shared with the homepage -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;700&amp;family=Suez+One&amp;display=swap" rel="stylesheet" />

{GTAG}

  <style>{CSS}  </style>
</head>
<body>

{nav}

  <main class="wrap">
    <article>
{body}
    </article>
  </main>

{footer}

{TRACKING}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# City data. "in" is the city with the ב prefix, "to" with ל.
# ---------------------------------------------------------------------------

CITIES = [
    {
        "slug": "tel-aviv",
        "name": "תל אביב",
        "in": "בתל אביב",
        "to": "לתל אביב",
        "card": "דירות ותיקות, בניינים בלי מעלית, ועיר שבה כל רהיט כבד עולה כסף להוציא.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות בתל אביב: ליאור בוכשטב מגיעה לדירה, אומרת מה שווה ומה לא, ומלווה את המכירה ברשת, בבית פתוח או במכירה פומבית.",
        "lead": "בתל אביב, יותר מבכל מקום אחר באזור, הוצאה של רהיט מדירה עולה כסף: קומות בלי מעלית, רחובות בלי חניה ומנוף שצריך להזמין מראש. לכן הצעד הראשון הוא לדעת מה שווה להוציא ולמכור, ומה לא.",
        "local_h2": "מה נמצא בדירות הוותיקות של תל אביב",
        "local": [
            "רבות מהדירות בתל אביב נבנו בשנות השלושים עד השישים, חלקן בבנייני \"העיר הלבנה\" שהוכרזה ב-2003 כאתר מורשת עולמית של אונסק\"ו. בדירה שבה משפחה גרה עשרות שנים נפוץ למצוא רהיטים ישראליים משנות החמישים והשישים, קרמיקה ישראלית, ספרייה גדולה ותמונות ממוסגרות שנקנו מאמנים מקומיים.",
            "לא כל אלה שווים כסף. רהיט ישראלי פשוט ממשרד או מחדר שינה שווה בדרך כלל מעט, וקרמיקה מסומנת, ציור חתום או פריט עיצוב מוכר יכולים להפתיע. ההבדל ביניהם לא נראה מהמסדרון, ולכן כדאי לבדוק לפני שמזמינים פינוי.",
        ],
        "logistics": "בבניין בלי מעלית, הוצאה של מזנון, פסנתר או ארון כבד עולה לא פעם יותר ממה שהפריט שווה. לפני שמשלמים על סבלות כדאי לדעת אם יש מה למכור, ואם לא, לחשוב על תרומה שהעמותה אוספת בעצמה. <a href=\"/guides/heavy-items-worth-least/\">למה הפריטים הכבדים שווים הכי פחות</a>.",
        "faq": ("כדאי למכור רהיט כבד מדירה בלי מעלית?", "רק אם הוא שווה יותר ממה שעולה להוריד אותו. ברוב המקרים רהיטים כבדים ומסיביים שווים מעט, ועדיף לבדוק את זה לפני שמזמינים סבלים או מנוף."),
        "neighbors": ["ramat-hasharon", "herzliya"],
        "image": ("item-08", 854, 640, "מזנון תצוגה עתיק מעץ לצד כיסא"),
        "guides": ["heavy-items-worth-least", "porcelain-and-ceramics-value", "framed-art-value"],
    },
    {
        "slug": "ramat-hasharon",
        "name": "רמת השרון",
        "in": "ברמת השרון",
        "to": "לרמת השרון",
        "card": "בתים פרטיים עם מחסן, בוידעם ומרתף, ותכולה של חיים שלמים.",
        "desc": "הערכת ומכירת תכולת בית ועזבונות ברמת השרון: ליאור בוכשטב עוברת על התכולה, כולל מחסן ובוידעם, אומרת מה שווה ומלווה את המכירה.",
        "lead": "ברמת השרון הרבה מהעבודה היא בבתים פרטיים, ובבית פרטי התכולה גדולה יותר: מחסן בחצר, בוידעם, מרתף. שם, רחוק מהעין, נשמרים הרבה פעמים הפריטים שאף אחד לא פתח שנים.",
        "local_h2": "בית פרטי ברמת השרון: הערך מסתתר במחסן",
        "local": [
            "רמת השרון התחילה בשנות העשרים כמושבה קטנה, ועד היום חלק גדול ממנה הוא בתים פרטיים וצמודי קרקע שמשפחות גרו בהם עשרות שנים. בבית כזה התכולה מתפרסת על כמה קומות ועל מחסנים, ולא פעם יש בו שכבות של דורות: הרהיטים של ההורים, הסרוויז מהחתונה וקופסאות שהגיעו מדירה אחרת במשפחה.",
            "בבית פרטי הפריטים המעניינים נמצאים פחות בסלון ויותר במקומות שאיש לא נכנס אליהם: ארגזים בבוידעם, ארון במרתף, מגירות בשידה ישנה. לכן הבדיקה כוללת את כל החללים, לא רק את מה שעומד על הוויטרינה.",
        ],
        "logistics": "לפני שמזמינים פינוי לבית פרטי, כדאי לעבור על המחסן והבוידעם לפי רשימה מסודרת. <a href=\"/guides/before-clearance-checklist/\">הצ'קליסט המלא לפני פינוי</a>.",
        "faq": ("מה כדאי לבדוק במחסן ובבוידעם לפני פינוי?", "ארגזים סגורים, קופסאות עם כלים עטופים, ציורים שהורדו מהקיר, ספרים ישנים ומגירות של רהיטים ישנים. אלה המקומות שבהם נשמרים לא פעם הפריטים ששווים בדיקה."),
        "testimonial": ("להיפרד מתכולת בית הילדות זה טיפ-טיפה עצוב, מוכרחה להודות שבזכות ליאור החפצים קיבלו את הכבוד הראוי להם ועברו לחיות בבתים אוהבים חדשים. כל התהליך נעשה ברגישות ויחד עם זאת במקצועיות והקפדה על הפרטים ובסה\"כ נתן תחושה של עזרה והקלה גדולה. הגעתי לליאור במקרה אבל כנראה שאין מקריות — ממליצה בחום!", "מיכל, רמת השרון"),
        "neighbors": ["tel-aviv", "herzliya", "raanana"],
        "image": ("item-03", 640, 854, "שידת עץ עתיקה עם מראה ומגירות"),
        "guides": ["before-clearance-checklist", "is-it-valuable-signs", "dividing-contents-between-heirs"],
    },
    {
        "slug": "herzliya",
        "name": "הרצליה",
        "in": "בהרצליה",
        "to": "להרצליה",
        "card": "מהבתים הוותיקים במרכז העיר ועד הווילות בהרצליה פיתוח, עם אוספים שנצברו שנים.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות בהרצליה ובהרצליה פיתוח: זיהוי כלי כסף, קריסטל, ציורים ורהיטים, וליווי המכירה.",
        "lead": "בהרצליה יש שני סוגי בתים: הבתים והדירות הוותיקים במרכז העיר, והבתים הגדולים בהרצליה פיתוח. בשניהם נאספים לאורך השנים חפצים שנקנו בנסיעות ונשמרו בוויטרינה, ושם כדאי להתחיל לבדוק.",
        "local_h2": "אוספים שנצברו שנים: כסף, קריסטל וציורים",
        "local": [
            "הרצליה נוסדה ב-1924 כמושבה חקלאית, וגדלה לעיר שבה שכונות ותיקות יושבות לצד אזורי וילות. בבית גדול שמשפחה גרה בו הרבה שנים נצברים לא פעם אוספים: מערכת כלי כסף, כוסות קריסטל, ציורים ממוסגרים ופסלונים שנקנו בחו\"ל.",
            "הטעות הנפוצה בבתים כאלה היא להניח שהכול יקר. חלק גדול מכלי ה\"כסף\" הוא בעצם ציפוי, וקריסטל רגיל שווה פחות ממה שנדמה. מצד שני, פריט אחד חתום או מסומן יכול להיות שווה יותר מכל השאר יחד. בדיקה מסודרת מפרידה ביניהם.",
        ],
        "logistics": "לפני שמחליטים על ערוץ מכירה, כדאי להבין מה בדיוק יש: <a href=\"/guides/silver-and-metalware-value/\">איך מבדילים בין כסף לציפוי</a>, ו<a href=\"/guides/crystal-and-glass-value/\">כמה שווה קריסטל ישן</a>.",
        "faq": ("איך יודעים אם כלי כסף בבית הם כסף אמיתי?", "מחפשים חותמת: 925, 900 או 800 הם כסף; EPNS, Silver Plated או A1 הם ציפוי על מתכת בסיס. לא כדאי לצחצח או למכור לפני שקוראים את החותמות."),
        "neighbors": ["ramat-hasharon", "raanana", "tel-aviv"],
        "image": ("item-15", 854, 640, "כוסות יין מזכוכית קריסטל מעוטרת"),
        "guides": ["silver-and-metalware-value", "crystal-and-glass-value", "how-to-sell-apartment-contents"],
    },
    {
        "slug": "raanana",
        "name": "רעננה",
        "in": "ברעננה",
        "to": "לרעננה",
        "card": "בתים של משפחות עולים, עם רהיטים, סרוויזים וספרים שהגיעו בקונטיינר מחו\"ל.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות ברעננה: רהיטים, סרוויזים, ספרים ופריטים שהגיעו מחו\"ל. ליאור בוכשטב אומרת מה שווה בשוק הישראלי ומלווה את המכירה, בלי לקנות את התכולה.",
        "lead": "ברעננה יש הרבה בתים של משפחות שעלו מארצות דוברות אנגלית, והביאו איתן תכולה שלמה מחו\"ל. הערך של פריטים כאלה נקבע לפי הביקוש כאן בארץ, ולא לפי מה ששילמו עליהם בזמנו, וזה ההבדל שכדאי לבדוק.",
        "local_h2": "פריטים שהגיעו מחו\"ל: מה שווה כאן ומה לא",
        "local": [
            "רעננה נוסדה ב-1922 על ידי קבוצת מתיישבים מניו יורק, ועד היום יש בה קהילה גדולה של עולים מארצות הברית, מבריטניה ומדרום אפריקה. בבתים של משפחות עולים נפוץ למצוא פריטים שהגיעו בקונטיינר: רהיטים בסגנון אנגלי או אמריקאי, סרוויזים של בתי חרושת אירופיים, תמונות ממוסגרות וספרייה באנגלית.",
            "חלק מהפריטים האלה שווים יפה גם בישראל, וחלק פחות: רהיט כבד בסגנון קלאסי, למשל, קשה למכור כאן כמעט בכל מחיר. מותג מוכר של פורצלן או ציור של אמן ידוע יכולים לעניין קונים. השאלה איפה למכור (כאן, או לקונים בחו\"ל ברשת) היא חלק מההמלצה.",
        ],
        "logistics": "ספרים באנגלית הם מקרה מיוחד: יש להם קהל בארץ, אבל מצומצם. <a href=\"/guides/inherited-library-books/\">מה עושים עם ספרייה שירשתם</a>.",
        "faq": ("האם פריטים שהגיעו מחו\"ל שווים יותר?", "לא בהכרח. הערך נקבע לפי המותג, המצב והביקוש בשוק שבו מוכרים. רהיטים כבדים בסגנון קלאסי קשים למכירה בישראל, וסרוויז ממותג מוכר או ציור חתום יכולים לעניין קונים."),
        "neighbors": ["kfar-saba", "herzliya", "hod-hasharon"],
        "image": ("item-14", 854, 640, "מערכת צלחות פורצלן עם עיטורי פרחים"),
        "guides": ["porcelain-and-ceramics-value", "inherited-library-books", "vintage-furniture-value"],
    },
    {
        "slug": "kfar-saba",
        "name": "כפר סבא",
        "in": "בכפר סבא",
        "to": "לכפר סבא",
        "card": "שכונות ותיקות ובתים שאותה משפחה גרה בהם כמעט כל חייה.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות בכפר סבא: מיון מסודר של תכולה של שנים, זיהוי מה שווה ומה לא, וליווי המכירה.",
        "lead": "בכפר סבא הרבה מהדירות והבתים הם של משפחות שגרו בהם כמעט כל חייהן. תכולה כזו נבנית שכבה על שכבה, ולכן המשימה הראשונה היא לא למכור, אלא למיין: מה למשפחה, מה לבדיקה, מה לתרומה.",
        "local_h2": "תכולה של חיים שלמים: למיין לפני שמוכרים",
        "local": [
            "כפר סבא נוסדה ב-1903 כמושבה מוקפת פרדסים, ובשכונות הוותיקות שלה יש הרבה בתים ודירות שאותה משפחה החזיקה עשרות שנים. בבית כזה נמצאים זה לצד זה הרהיטים מהחתונה, הכלים שנקנו בשנות השבעים, המתנות של הנכדים והקופסאות שאף אחד לא פתח.",
            "כשיש כמה אחים ויורשים, המיון הוא גם השלב שבו הכי קל לריב. כדאי לקבוע מראש איך בוחרים מזכרות, ולדעת מה שווה כסף לפני שמחלקים, כדי שאף אחד לא ירגיש שקיבל פחות.",
        ],
        "logistics": "סדר עבודה שמונע ריבים ויקר פחות: מסמכים ותמונות, מזכרות למשפחה, בדיקת ערך, מכירה, תרומה, ורק בסוף פינוי. <a href=\"/guides/dividing-contents-between-heirs/\">איך מחלקים תכולה בין יורשים בלי ריב</a>.",
        "faq": ("איך מחלקים תכולה בין אחים לפני שמוכרים?", "קודם יודעים מה שווה כסף, ואז מחלקים. כשכולם רואים את אותה הערכה, קל יותר להסכים על מזכרות ועל מה נמכר, ואף אחד לא מרגיש שקיבל פחות."),
        "neighbors": ["raanana", "hod-hasharon"],
        "image": ("item-05", 853, 640, "מזנון עץ עתיק עם גילופים ומגירות"),
        "guides": ["dividing-contents-between-heirs", "inherited-apartment-contents", "sell-donate-or-keep"],
    },
    {
        "slug": "hod-hasharon",
        "name": "הוד השרון",
        "in": "בהוד השרון",
        "to": "להוד השרון",
        "card": "ארבעה יישובים ותיקים שהתאחדו לעיר אחת, ובתים עם חצר ומחסן.",
        "desc": "הערכת ומכירת תכולת בית ועזבונות בהוד השרון: מגדיאל, רמתיים, הדר ורמת הדר. ליאור בוכשטב עוברת על התכולה, אומרת מה שווה ומלווה את המכירה, בלי לקנות את הפריטים.",
        "lead": "בהוד השרון, בעיקר בשכונות הוותיקות, יש הרבה בתים חד-משפחתיים עם חצר ומחסן. ברוב המקרים התכולה גדולה ממה שנדמה, ואין סיבה למהר לפנות לפני שיודעים מה יש.",
        "local_h2": "שכונות ותיקות, בתים עם חצר",
        "local": [
            "הוד השרון קמה ב-1964 מאיחוד של ארבעה יישובים ותיקים: מגדיאל, רמתיים, הדר ורמת הדר. בשכונות שצמחו מהם עדיין עומדים בתים חד-משפחתיים, חלקם בני עשרות שנים, עם מחסן בחצר ולפעמים יחידה נוספת שבה גרו בני משפחה.",
            "בבתים כאלה פוגשים לא פעם רהיטים ישנים מעץ מלא, כלי עבודה, כלים ישנים וחפצים שעברו בין דורות. חלקם רק נראים ישנים, וחלקם באמת שווים בדיקה. ההבדל הוא בסימנים: חותמת, חתימה, סוג העץ ואופן ההרכבה.",
        ],
        "logistics": "הסימנים הראשונים שכדאי לחפש בעצמכם, לפני שמישהו מגיע: <a href=\"/guides/is-it-valuable-signs/\">10 סימנים שאולי ירשתם משהו ששווה כסף</a>.",
        "faq": ("איך יודעים אם רהיט ישן שווה משהו?", "בודקים שם יצרן, תקופה, עץ מלא מול ציפוי, חיבורי נגרות וגימור מקורי. לרהיטי עיצוב משנות החמישים והשישים יש שוק, ולרהיטים כבדים ומגולפים כמעט אין."),
        "neighbors": ["kfar-saba", "raanana"],
        "image": ("item-10", 854, 640, "רהיט עץ עתיק עם מדף ועמודים מגולפים"),
        "guides": ["is-it-valuable-signs", "vintage-furniture-value", "what-affects-value"],
    },
    {
        "slug": "netanya",
        "name": "נתניה",
        "in": "בנתניה",
        "to": "לנתניה",
        "card": "דירות של משפחות עולים, עם כלי כסף, פורצלן אירופי ופריטים מהבית הקודם.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות בנתניה: זיהוי כלי כסף מול ציפוי, פורצלן אירופי, תמונות ורהיטים, וליווי המכירה.",
        "lead": "בנתניה הרבה דירות שייכות למשפחות עולים, שהביאו איתן פריטים מהבית הקודם. בדירות כאלה ההבדל הגדול בערך הוא לא פעם בין כלי כסף אמיתי לכלי מצופה, ושווה לבדוק אותו לפני שמוכרים או מפנים.",
        "local_h2": "פריטים שהגיעו עם העלייה",
        "local": [
            "נתניה נוסדה ב-1929, וקלטה לאורך השנים גלי עלייה גדולים: מצפון אפריקה, מברית המועצות לשעבר ובעשורים האחרונים גם מצרפת. בדירות של משפחות עולים נפוץ למצוא פריטים שהגיעו איתן: כלי כסף או כלים מצופים כסף, פורצלן אירופי, שעונים, תמונות ממוסגרות וספרים בשפת המקור.",
            "בדירות כאלה, הרבה פעמים מה שנראה הכי יקר שווה הכי מעט, ולהפך. סט סכו\"ם מבריק עשוי להיות ציפוי, וקופסה קטנה ומושחרת במגירה עשויה להיות כסף. לפני שמחליטים, כדאי לבדוק את החותמות.",
        ],
        "logistics": "איך לקרוא את החותמות לבד, ומה המשמעות של כל סימון: <a href=\"/guides/silver-and-metalware-value/\">כלי כסף או ציפוי</a>.",
        "faq": ("האם כדאי למכור כלי כסף לפי משקל?", "רק אם זה באמת כסף ואין לכלי ערך אספני. מכירה לפי משקל מתאימה לכסף פגום או רגיל. כלי של יצרן מוכר או פריט מעוצב שווה בדרך כלל יותר כפריט מאשר כמתכת."),
        "neighbors": ["hadera", "kfar-saba", "raanana"],
        "image": ("item-11", 854, 640, "כלי מתכת ישן בן שלוש קומות עם עיטורים"),
        "guides": ["silver-and-metalware-value", "porcelain-and-ceramics-value", "what-affects-value"],
    },
    {
        "slug": "hadera",
        "name": "חדרה",
        "in": "בחדרה",
        "to": "לחדרה",
        "card": "אחת המושבות הוותיקות בארץ, ובתים שעברו בין דורות.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות בחדרה: ליאור בוכשטב מעריכה את התכולה, אומרת מה שווה ומה לא, ומלווה את המכירה ברשת, בבית פתוח או במכירה פומבית.",
        "lead": "בחדרה, אחת המושבות הוותיקות בארץ, יש בתים שעברו בין כמה דורות של אותה משפחה. בתכולה כזו יש לא פעם פריטים ישנים באמת, לצד הרבה דברים שרק נראים ישנים, ושווה לדעת מה מה לפני שמחליטים.",
        "local_h2": "בית שעבר בין דורות",
        "local": [
            "חדרה נוסדה ב-1891, ומאז גדלה ממושבה חקלאית לעיר. בבתים הוותיקים שלה, ובדירות של משפחות שגרו בה עשרות שנים, אפשר למצוא רהיטים שעברו מהורים לילדים, כלים ישנים, תמונות ומסמכים שמספרים את סיפור המשפחה.",
            "דווקא בבית כזה חשוב לא לזרוק דבר לפני מיון. מסמכים, מכתבים ותמונות שווים למשפחה יותר מכל דבר אחר, וחלק מהחפצים הישנים יכולים לעניין קונים ואספנים.",
        ],
        "logistics": "אם הבית צריך להתפנות ואתם לא יודעים מאיפה להתחיל: <a href=\"/guides/inherited-apartment-contents/\">מה עושים עם תכולת דירה של נפטר, צעד אחר צעד</a>.",
        "faq": ("מה לא לזרוק לפני מיון של בית ישן?", "מסמכים, מכתבים, אלבומים ותמונות, ציורים (גם כשהם נראים פשוטים), כלים עטופים בארגזים, שעונים ותכשיטים, וספרים ישנים. אחרי שאלה נבדקו, אפשר להחליט על השאר."),
        "testimonial": ("החוויה של העבודה עם ליאור היתה מצוינת. בעין המקצועית שלה היא ראתה מעבר לחפצים וידעה לשייך את החפץ הנכון לאדם הנכון ולצרכיו. ההתקשרות שלנו היתה על בסיס המלצות ולא בכדי — לכן אני מרשה לעצמי להמשיך ולהמליץ: תנו לליאור למצוא לחפצים שלכם בתים אוהבים לפחות כמו זה שלכם.", "ליאת, חדרה"),
        "neighbors": ["netanya", "zichron-yaakov"],
        "image": ("item-06", 854, 640, "אוסף מקלות הליכה ישנים מעץ"),
        "guides": ["inherited-apartment-contents", "is-it-valuable-signs", "sell-donate-or-keep"],
    },
    {
        "slug": "zichron-yaakov",
        "name": "זכרון יעקב",
        "in": "בזכרון יעקב",
        "to": "לזכרון יעקב",
        "card": "בתים ותיקים במושבה, ופריטים שנאספו לאורך דורות.",
        "desc": "הערכת ומכירת תכולת בית ועזבונות בזכרון יעקב: ליאור בוכשטב מזהה מה שווה בדיקה בתכולה של בית ותיק, ומלווה את המכירה לקונים בשוק.",
        "lead": "בזכרון יעקב יש בתים ותיקים שבהם נשמרים פריטים מכמה דורות, לצד בתים חדשים יותר של משפחות שבחרו לגור במושבה. בשני המקרים כדאי לבדוק מה שווה לפני שמחליטים מה עושים עם התכולה.",
        "local_h2": "בית במושבה: דורות של חפצים",
        "local": [
            "זכרון יעקב נוסדה ב-1882, מהמושבות הראשונות בארץ, ונבנתה בתמיכת הברון רוטשילד. בבתים ותיקים במושבה נשמרים לפעמים פריטים ממש ישנים, לצד רהיטים, כלים ותמונות שנאספו במשך דורות, ולא פעם גם ספרייה גדולה.",
            "בבית כזה אין דרך לדעת מבחוץ מה שווה. ארון פשוט יכול להיות רהיט ישן ומבוקש, וויטרינה מלאה יכולה להיות שווה מעט. עין מקצועית חוסכת גם זריקה של משהו יקר וגם מאמץ מכירה על משהו שאין לו קונים.",
        ],
        "logistics": "כדי להבין מה בכלל קובע ערך, לפני שמישהו מגיע: <a href=\"/guides/what-affects-value/\">מצב, נדירות, מקור, ביקוש ושלמות</a>.",
        "faq": ("כמה זמן לוקח למכור תכולה של בית?", "תלוי בערוץ: פריטים מבוקשים נמכרים ברשת לעיתים תוך ימים, מכירת בית פתוחה מרוקנת את הבית ביום אחד אחרי הכנה, ומכירה פומבית מתוכננת לכמה שבועות. מה שמאריך את התהליך הוא בעיקר אחסון \"עד שנחליט\"."),
        "neighbors": ["haifa", "hadera"],
        "image": ("item-04", 640, 854, "תמונה ממוסגרת של האל גנש"),
        "guides": ["what-affects-value", "how-long-does-selling-contents-take", "framed-art-value"],
    },
    {
        "slug": "haifa",
        "name": "חיפה",
        "in": "בחיפה",
        "to": "לחיפה",
        "card": "הדר, הכרמל והמושבה הגרמנית: פורצלן אירופי, רהיטי עץ כבדים וספריות.",
        "desc": "הערכת ומכירת תכולת דירה ועזבונות בחיפה: הדר הכרמל, הכרמל והמושבה הגרמנית. ליאור בוכשטב מזהה פורצלן, רהיטים, ספרים ותמונות, ומלווה את המכירה בלי לקנות את התכולה.",
        "lead": "בחיפה הרבה מהדירות הוותיקות נמצאות בשכונות שנבנו בשנות העשרים והשלושים, על מדרון ובלי מעלית. בדירות כאלה יש לא פעם פריטים מעניינים, וגם רהיטים כבדים שעולה יותר להוריד מאשר הם שווים.",
        "local_h2": "הדר, הכרמל והמושבה הגרמנית",
        "local": [
            "בשכונות הוותיקות של חיפה, כמו הדר הכרמל, מרכז הכרמל והמושבה הגרמנית, יש דירות של משפחות שהגיעו בשנות השלושים מגרמניה וממרכז אירופה. בבתים כאלה נפוץ למצוא פורצלן אירופי, רהיטי עץ כבדים, ספרייה בגרמנית ותמונות ממוסגרות.",
            "פורצלן של בית חרושת מוכר יכול לעניין קונים, בעיקר כשהמערכת שלמה. רהיטים כבדים כהים, לעומת זאת, מבוקשים היום מעט, ובבניין על מדרון בלי מעלית ההורדה שלהם עולה כסף. כדאי לדעת את ההבדל לפני שמזמינים הובלה.",
        ],
        "logistics": "ספרים בגרמנית ובשפות אחרות: למי הם מעניינים ואיך מוכרים אותם. <a href=\"/guides/inherited-library-books/\">מה עושים עם ספרייה שירשתם</a>.",
        "faq": ("מה עושים עם ספרים ישנים בגרמנית?", "בודקים קודם אם יש ביניהם ספרים ישנים או נדירים, מהדורות ראשונות או ספרים עם הקדשות. לספרים כאלה יש קונים ואספנים. את השאר אפשר לתרום לספריות ולמוסדות שאוספים ספרים בשפות זרות."),
        "neighbors": ["zichron-yaakov"],
        "image": ("item-19", 854, 640, "קנקן וקערית פורצלן בעיטור פירות"),
        "guides": ["porcelain-and-ceramics-value", "inherited-library-books", "heavy-items-worth-least"],
    },
]

GUIDE_TITLES = {
    "heavy-items-worth-least": "מה עושים עם פסנתר ישן, מזנון וסרוויז שירשתם?",
    "porcelain-and-ceramics-value": "כמה שווה מערכת פורצלן ישנה? כולל נעמן ולפיד",
    "framed-art-value": "כמה שווה תמונה ממוסגרת ישנה?",
    "before-clearance-checklist": "לפני שמזמינים פינוי דירה: הצ'קליסט המלא",
    "is-it-valuable-signs": "10 סימנים שאולי ירשתם משהו ששווה כסף",
    "dividing-contents-between-heirs": "איך מחלקים תכולת דירה בין יורשים בלי ריב?",
    "silver-and-metalware-value": "הערכת כלי כסף: כסף או ציפוי, ואיך יודעים כמה זה שווה",
    "crystal-and-glass-value": "כמה שווה קריסטל ישן?",
    "how-to-sell-apartment-contents": "איך מוכרים תכולת דירה? ברשת, בבית פתוח או במכירה פומבית",
    "inherited-library-books": "ירשתם ספרייה? מה עושים עם ספרים ישנים",
    "vintage-furniture-value": "כמה שווה רהיט עתיק?",
    "inherited-apartment-contents": "מה עושים עם תכולת דירה של נפטר?",
    "sell-donate-or-keep": "ירושה: למכור, לתרום או לשמור?",
    "what-affects-value": "מה קובע כמה שווה פריט ישן?",
    "how-long-does-selling-contents-take": "כמה זמן לוקח למכור תכולת דירה?",
}

BY_SLUG = {city["slug"]: city for city in CITIES}

NAV_AREA = """  <nav class="top-strip" aria-label="ניווט פירורי לחם">
    <a href="https://www.bamegirot.com/">→ במגירות — הערכת ומכירת תכולת דירה ועזבונות</a>
    <span class="top-strip-sep" aria-hidden="true">·</span>
    <a href="/areas/">אזורי שירות</a>
    <span class="top-strip-sep" aria-hidden="true">·</span>
    <a href="/guides/">מדריכים</a>
  </nav>"""


def city_page(city: dict, dates: tuple[str, str]) -> str:
    url = f"{BASE}areas/{city['slug']}/"
    name, where = city["name"], city["in"]
    h1 = f"הערכת ומכירת תכולת דירה ועזבונות {where}"
    title = f"{h1} | במגירות"
    faq = [
        (
            f"האם את מגיעה {city['to']}?",
            f"כן. {name} נמצאת באזור השירות שלי, מתל אביב ועד חיפה. אפשר להתחיל בכמה תמונות בוואטסאפ, ואם יש מה לבדוק אני מגיעה לדירה, ללא התחייבות.",
        ),
        city["faq"],
    ]
    img, w, h, alt = city["image"]
    testimonial = ""
    if city.get("testimonial"):
        quote, who = city["testimonial"]
        testimonial = f"""
      <h2>מה אמרו משפחות {where}</h2>
      <blockquote class="quote">
        <p>{quote}</p>
        <cite>{who}</cite>
      </blockquote>"""
    neighbors = "\n".join(
        f'          <li><a href="/areas/{slug}/">הערכת ומכירת תכולת דירה {BY_SLUG[slug]["in"]}</a></li>'
        for slug in city["neighbors"]
    )
    guides = "\n".join(
        f'          <li><a href="/guides/{slug}/">{GUIDE_TITLES[slug]}</a></li>' for slug in city["guides"]
    )
    local = "\n".join(f"      <p>{p}</p>" for p in city["local"])
    body = f"""      <h1>{h1}</h1>
      <p class="byline"><a href="/about/">ליאור בוכשטב</a> · במגירות · מתל אביב ועד חיפה · {visible_label(dates[1])}</p>

      <div class="callout">
        <p><strong>בקצרה:</strong> אני מגיעה לדירות ולבתים {where}, עוברת על התכולה ואומרת מה שווה בדיקה ומה לא, ממליצה איפה ואיך למכור, ומלווה את המכירה ברשת, במכירת בית פתוחה או במכירה פומבית. הצעד הראשון: כמה תמונות בוואטסאפ.</p>
      </div>
      <p>{city['lead']}</p>

      <h2>{city['local_h2']}</h2>
{local}

      <figure class="photo">
        <img src="/images/{img}.webp" alt="{alt}" width="{w}" height="{h}" loading="lazy" decoding="async" />
        <figcaption>{alt}: פריט שמצא בית חדש, מתוך תכולות שליוויתי למכירה.</figcaption>
      </figure>

      <h2>איך זה עובד {where}</h2>
      <ol>
        <li><strong>שולחים תמונות.</strong> כמה תמונות בוואטסאפ של החדרים, הוויטרינה והפריטים שאתם לא בטוחים לגביהם. כבר מזה אפשר להבין אם יש מה לבדוק.</li>
        <li><strong>אני מגיעה לדירה.</strong> עוברת על התכולה, כולל ארונות, מגירות ומחסן, ואומרת בכנות מה שווה ומה פחות.</li>
        <li><strong>מוכרים, בליווי.</strong> לכל פריט הערוץ שמתאים לו: מכירה ברשת, מכירת בית פתוחה או מכירה פומבית. אני מלווה את המכירה, ואתם מחליטים בכל שלב.</li>
      </ol>
      <p>{city['logistics']}</p>

      <h2>מה עושים עם מה שלא נמכר</h2>
      <p>כמעט בכל דירה נשארים פריטים שאין להם קונה. בגדים, כלי בית ורהיטים שימושיים אפשר לתרום לעמותות, ורבות מהן אוספות בעצמן. את מה שנשאר אחרי זה אפשר לפנות דרך שירות איסוף הפסולת הגושנית של עיריית {name} או בחברת פינוי, כשכבר ברור שלא נזרק שום דבר בעל ערך. <a href="/guides/sell-donate-or-keep/">איך מחליטים מה למכור, מה לתרום ומה לשמור</a>.</p>
{testimonial}
      <h2>שאלות נפוצות על הערכת תכולה {where}</h2>
{faq_html(faq)}

      <div class="next-reads">
        <h2>מדריכים שיעזרו לכם</h2>
        <ul>
{guides}
        </ul>
        <h2>אזורים סמוכים</h2>
        <ul>
{neighbors}
          <li><a href="/areas/">כל אזורי השירות, מתל אביב ועד חיפה</a></li>
        </ul>
      </div>
{cta(f"יש לכם תכולת דירה {where}?", "שלחו לי כמה תמונות בוואטסאפ, ואגיד לכם בכנות אם יש מה לבדוק. ללא התחייבות.", f"שלום ליאור, הגעתי דרך האתר במגירות. יש לי תכולת דירה {where} ואשמח לייעוץ")}"""
    graph = [
        {
            "@type": "WebPage",
            "@id": f"{url}#webpage",
            "url": url,
            "name": h1,
            "description": city["desc"],
            "inLanguage": "he-IL",
            "isPartOf": {"@id": f"{BASE}#website"},
            "about": {"@id": f"{url}#service"},
            "author": AUTHOR,
            "primaryImageOfPage": {"@type": "ImageObject", "url": f"{BASE}images/{img}.webp", "width": w, "height": h},
            "datePublished": dates[0],
            "dateModified": dates[1],
        },
        {
            "@type": "Service",
            "@id": f"{url}#service",
            "name": h1,
            "serviceType": "הערכת ומכירת תכולת דירה ועזבונות, עתיקות ופריטי וינטג׳",
            "provider": {"@id": f"{BASE}#business"},
            "areaServed": {"@type": "City", "name": name, "containedInPlace": {"@type": "Country", "name": "ישראל"}},
            "url": url,
        },
        breadcrumbs(url, [("במגירות", BASE), ("אזורי שירות", f"{BASE}areas/"), (name, None)]),
        faq_entity(url, faq),
    ]
    return shell(
        url=url, title=title, description=city["desc"], og_title=h1, og_type="website",
        graph=graph, nav=NAV_AREA, body=body,
    )


def hub_page(dates: tuple[str, str]) -> str:
    url = f"{BASE}areas/"
    h1 = "הערכת ומכירת תכולת דירה ועזבונות מתל אביב ועד חיפה: אזורי שירות"
    desc = "ליאור בוכשטב מעריכה תכולת דירה ועזבונות ומלווה את המכירה בתל אביב, רמת השרון, הרצליה, רעננה, כפר סבא, הוד השרון, נתניה, חדרה, זכרון יעקב וחיפה."
    cards = "\n".join(
        f'        <li><a href="/areas/{c["slug"]}/"><strong>{c["name"]}</strong><span>{c["card"]}</span></a></li>'
        for c in CITIES
    )
    body = f"""      <h1>{h1}</h1>
      <p class="byline"><a href="/about/">ליאור בוכשטב</a> · במגירות · {visible_label(dates[1])}</p>
      <div class="callout">
        <p><strong>בקצרה:</strong> אני מגיעה לדירות ולבתים לאורך מישור החוף, מתל אביב ועד חיפה: מעריכה את התכולה, אומרת מה שווה ומה לא, ומלווה את המכירה. לא מצאתם את העיר שלכם ברשימה? שלחו הודעה, ונבדוק יחד.</p>
      </div>
      <p>לכל עיר יש אופי משלה: דירות ותיקות בלי מעלית בתל אביב ובחיפה, בתים פרטיים עם מחסן ובוידעם בשרון, ובתים של משפחות עולים שהביאו איתן תכולה שלמה מחו"ל. בעמוד של כל עיר תמצאו מה נפוץ למצוא שם, ומה כדאי לבדוק לפני שמזמינים פינוי.</p>
      <ul class="card-list">
{cards}
      </ul>
{cta("לא בטוחים אם אני מגיעה אליכם?", "שלחו לי הודעה עם העיר וכמה תמונות, ואחזור אליכם. ללא התחייבות.", "שלום ליאור, הגעתי דרך האתר במגירות ואשמח לבדוק אם את מגיעה לאזור שלי")}"""
    graph = [
        {
            "@type": "CollectionPage",
            "@id": f"{url}#webpage",
            "url": url,
            "name": h1,
            "description": desc,
            "inLanguage": "he-IL",
            "isPartOf": {"@id": f"{BASE}#website"},
            "about": {"@id": f"{BASE}#business"},
            "mainEntity": {"@id": f"{url}#areas"},
            "datePublished": dates[0],
            "dateModified": dates[1],
        },
        {
            "@type": "ItemList",
            "@id": f"{url}#areas",
            "numberOfItems": len(CITIES),
            "itemListElement": [
                {"@type": "ListItem", "position": i, "url": f"{BASE}areas/{c['slug']}/", "name": f"הערכת ומכירת תכולת דירה {c['in']}"}
                for i, c in enumerate(CITIES, 1)
            ],
        },
        breadcrumbs(url, [("במגירות", BASE), ("אזורי שירות", None)]),
    ]
    return shell(
        url=url, title="אזורי שירות: הערכת ומכירת תכולת דירה מתל אביב ועד חיפה | במגירות", description=desc,
        og_title=h1, og_type="website", graph=graph, nav=NAV_AREA, body=body,
    )


DATES_RE = re.compile(r'"datePublished": "(\d{4}-\d{2}-\d{2})",\s*"dateModified": "(\d{4}-\d{2}-\d{2})"')


def write_dated(path: pathlib.Path, render) -> bool:
    """Write ``render(dates)``; keep the old dates when the output is otherwise unchanged."""
    today = dt.date.today().isoformat()
    if path.exists():
        old = path.read_text(encoding="utf-8")
        match = DATES_RE.search(old)
        if match:
            kept = render((match.group(1), match.group(2)))
            if kept == old:
                return False
            path.write_text(render((match.group(1), today)), encoding="utf-8")
            return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render((today, today)), encoding="utf-8")
    return True


def main() -> int:
    changed = []
    if write_dated(ROOT / "areas" / "index.html", hub_page):
        changed.append("areas/index.html")
    for city in CITIES:
        path = ROOT / "areas" / city["slug"] / "index.html"
        if write_dated(path, lambda dates, c=city: city_page(c, dates)):
            changed.append(path.relative_to(ROOT).as_posix())
    print(f"area pages: {len(CITIES) + 1} total, {len(changed)} written")
    for rel in changed:
        print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
