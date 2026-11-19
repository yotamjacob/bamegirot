#!/usr/bin/env python3
"""Fast, dependency-free checks for the static production site."""

from __future__ import annotations

import html as html_lib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
CANONICAL_URL = "https://www.bamegirot.com/"
SEO_TITLE = "הערכת ומכירת תכולת דירה, עזבונות ועתיקות מתל אביב ועד חיפה | במגירות"
SEO_DESCRIPTION = (
    "ליאור בוכשטב מעריכה תכולת דירה, עזבונות ועתיקות ומלווה את המכירה של ציורים, "
    "כלי כסף, קרמיקה ורהיטי וינטג׳. מגיעה אליכם הביתה מתל אביב ועד חיפה, "
    "ללא התחייבות."
)
H1 = "מומחית לוינטאג׳ ישראלי ובינלאומי · קניית, מכירת והערכת עזבונות ותכולות בתים"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.fragments: list[str] = []
        self.local_assets: list[str] = []
        self.images: list[dict[str, str]] = []
        self.elements: dict[str, list[dict[str, str]]] = defaultdict(list)
        self.unsafe_blank_links: list[str] = []
        self.whatsapp_links: list[str] = []
        self.json_ld: list[str] = []
        self.inline_js: list[str] = []
        self._script_kind: str | None = None
        self._script_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs_raw: list[tuple[str, str | None]]) -> None:
        attrs = {key: value or "" for key, value in attrs_raw}
        self.elements[tag].append(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])

        if tag == "a":
            href = attrs.get("href", "")
            if href.startswith("#") and len(href) > 1:
                self.fragments.append(href[1:])
            if "wa.me/" in href:
                self.whatsapp_links.append(href)
            if attrs.get("target") == "_blank" and "noopener" not in attrs.get("rel", "").split():
                self.unsafe_blank_links.append(href)

        if tag == "img":
            self.images.append(attrs)

        reference = ""
        if tag in {"img", "script"}:
            reference = attrs.get("src", "")
        elif tag in {"link", "a"}:
            reference = attrs.get("href", "")
        if reference and self._is_local_file(reference):
            local_path = urlparse(reference).path.lstrip("/")
            if local_path:
                self.local_assets.append(local_path)

        if tag == "script" and not attrs.get("src"):
            self._script_kind = attrs.get("type", "text/javascript")
            self._script_buffer = []

    def handle_data(self, data: str) -> None:
        if self._script_kind is not None:
            self._script_buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "script" or self._script_kind is None:
            return
        source = "".join(self._script_buffer).strip()
        if self._script_kind == "application/ld+json":
            self.json_ld.append(source)
        elif source:
            self.inline_js.append(source)
        self._script_kind = None
        self._script_buffer = []

    @staticmethod
    def _is_local_file(reference: str) -> bool:
        parsed = urlparse(reference)
        return (
            not parsed.scheme
            and not parsed.netloc
            and not reference.startswith(("#", "data:", "mailto:", "tel:"))
            and bool(parsed.path)
        )


# Judaica and Jewish ritual objects are not offered (standing decisions
# 2026-10-30 and 2026-11-15: they attract the wrong enquiries).
JUDAICA_TERMS = ("יודאיקה", "ייעוד יהודי", "ספרי קודש", "חנוכי", "קידוש", "קופסאות בשמים", "Judaica")

# Lior does buy items (standing decision, 2026-11-19). The old "I don't buy the
# contents, so my appraisal is independent" positioning is retired and must not
# come back in any wording, Hebrew or English.
NOT_A_BUYER_TERMS = (
    "לא קונה את", "לא קונה תכולות", "לא קונה דבר", "אינה קונה", "אינני קונה",
    "לא קונים את התכולה", "בלי לקנות בעצמה", "נמכרים לקונים בשוק",
    "נשארת עצמאית", "ההערכה עצמאית", "ההערכה שלי עצמאית", "הערכה עצמאית",
    "בלתי תלוי", "בלי לקנות בעצמי", "קונה את הפריטים בעצמ", "קונה את התכולה בעצמ",
    "אין לי אינטרס במחיר נמוך", "אינטרס בקנייה",
    "never buys", "does not buy", "doesn't buy", "not buy", "stays independent",
)


# Generic "personal service" filler is not wanted (user decision, 2026-11-19):
# say something concrete (experience, area, what she checks) instead.
FILLER_TERMS = ("ליווי אישי", "שירות אישי", "לאורך כל התהליך", "לאורך כל הדרך", "ליווי צמוד", "יד ביד")

def normalized_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return " ".join(html_lib.unescape(without_tags).split())


def matching_attrs(
    parser: SiteParser,
    tag: str,
    attribute: str,
    value: str,
) -> list[dict[str, str]]:
    return [
        attrs
        for attrs in parser.elements.get(tag, [])
        if attrs.get(attribute, "").lower() == value.lower()
    ]


def check_javascript(sources: list[str], errors: list[str]) -> None:
    node = shutil.which("node")
    if not node:
        print("warning: Node.js not found; skipped inline JavaScript syntax checks")
        return
    for position, source in enumerate(sources, start=1):
        result = subprocess.run(
            [node, "--check", "-"],
            input=source,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            errors.append(f"inline JavaScript block {position} has invalid syntax:\n{detail}")


def check_guides(errors: list[str], homepage: str) -> None:
    """Every guide page and the hub: metadata, schema, links, and hub parity."""
    hub = ROOT / "guides" / "index.html"
    pages = sorted(ROOT.glob("guides/*/index.html"))
    events = sorted(ROOT.glob("events/*/index.html"))
    guide_urls = [f"{CANONICAL_URL}guides/{page.parent.name}/" for page in pages]

    area_hub = ROOT / "areas" / "index.html"
    areas = sorted(ROOT.glob("areas/*/index.html"))
    area_urls = [f"{CANONICAL_URL}areas/{page.parent.name}/" for page in areas]
    extra = [ROOT / "about" / "index.html", ROOT / "en" / "index.html", area_hub, *areas]

    for page in [hub, *pages, *events, *extra]:
        rel = page.relative_to(ROOT).as_posix()
        url = CANONICAL_URL + rel[: -len("index.html")]
        source = page.read_text(encoding="utf-8")
        parser = SiteParser()
        parser.feed(source)
        head = source.split("</head>", 1)[0]

        if len(re.findall(r"<title>", head)) != 1:
            errors.append(f"{rel}: must have exactly one <title>")
        if len(matching_attrs(parser, "meta", "name", "description")) != 1:
            errors.append(f"{rel}: must have exactly one meta description")
        canonicals = matching_attrs(parser, "link", "rel", "canonical")
        if len(canonicals) != 1 or canonicals[0].get("href") != url:
            errors.append(f"{rel}: canonical must be {url}")
        og_urls = matching_attrs(parser, "meta", "property", "og:url")
        if len(og_urls) != 1 or og_urls[0].get("content") != url:
            errors.append(f"{rel}: og:url must be {url}")
        if len(re.findall(r"<h1\b", source)) != 1:
            errors.append(f"{rel}: must have exactly one <h1>")

        missing_assets = sorted(
            reference
            for reference in set(parser.local_assets)
            if not (ROOT / reference).is_file()
            and not (ROOT / reference / "index.html").is_file()
        )
        if missing_assets:
            errors.append(f"{rel}: missing local assets: {', '.join(missing_assets)}")
        if parser.unsafe_blank_links:
            errors.append(f"{rel}: target=\"_blank\" links need rel=\"noopener\"")
        if not parser.whatsapp_links or any(
            "wa.me/972523321045" not in link for link in parser.whatsapp_links
        ):
            errors.append(f"{rel}: WhatsApp links must use the production number")
        for attrs in parser.images:
            if "alt" not in attrs or not attrs.get("width") or not attrs.get("height"):
                errors.append(f"{rel}: image needs alt, width and height: {attrs.get('src')}")

        graph: list[dict[str, object]] = []
        for payload in parser.json_ld:
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: JSON-LD is invalid: {exc}")
                continue
            graph.extend(item for item in parsed.get("@graph", []) if isinstance(item, dict))
        main_entity = next(
            (
                item
                for item in graph
                if item.get("@type") in ("Article", "CollectionPage", "Event", "ProfilePage", "WebPage")
            ),
            None,
        )
        if main_entity is None:
            errors.append(f"{rel}: JSON-LD needs an Article, CollectionPage, ProfilePage, WebPage or Event")
        elif main_entity["@type"] == "Event":
            for key in ("name", "startDate", "endDate", "location", "image"):
                if not main_entity.get(key):
                    errors.append(f"{rel}: Event needs {key}")
        else:
            if not main_entity.get("dateModified"):
                errors.append(f"{rel}: {main_entity['@type']} needs dateModified")
            if main_entity["@type"] == "Article":
                for key in ("headline", "datePublished", "author", "publisher", "image"):
                    if not main_entity.get(key):
                        errors.append(f"{rel}: Article needs {key}")
        if not any(item.get("@type") == "BreadcrumbList" for item in graph):
            errors.append(f"{rel}: BreadcrumbList is missing")

        faq = next((item for item in graph if item.get("@type") == "FAQPage"), None)
        if faq:
            visible_pairs = {
                (normalized_text(question), normalized_text(answer))
                for question, answer in re.findall(
                    r"<h3>(.*?)</h3>\s*<p>(.*?)</p>", source, flags=re.DOTALL
                )
            }
            for entity in faq.get("mainEntity", []):
                question = entity.get("name", "")
                accepted = entity.get("acceptedAnswer", {})
                answer = accepted.get("text", "") if isinstance(accepted, dict) else ""
                if (normalized_text(question), normalized_text(answer)) not in visible_pairs:
                    errors.append(f"{rel}: FAQ schema has no matching visible <h3>/<p>: {question}")

        if page == hub:
            item_list = next((item for item in graph if item.get("@type") == "ItemList"), None)
            if item_list is None:
                errors.append("guides/index.html: ItemList is missing")
            else:
                elements = item_list.get("itemListElement", [])
                listed = sorted(item.get("url") for item in elements)
                if item_list.get("numberOfItems") != len(pages) or listed != guide_urls:
                    errors.append(
                        "guides/index.html: ItemList must list every guide exactly once "
                        "with a matching numberOfItems"
                    )
                positions = [item.get("position") for item in elements]
                if positions != list(range(1, len(positions) + 1)):
                    errors.append("guides/index.html: ItemList positions must run 1..n")
            for guide_url in guide_urls:
                path = guide_url[len(CANONICAL_URL) - 1 :]
                if f'href="{path}"' not in source:
                    errors.append(f"guides/index.html: hub does not link to {path}")

    for guide_url in guide_urls:
        path = guide_url[len(CANONICAL_URL) - 1 :]
        if f'href="{path}"' not in homepage:
            errors.append(f"index.html: homepage does not link to {path}")

    # Service-area pages are generated by scripts/build_area_pages.py; the hub
    # must list every one of them and the homepage footer must link to each.
    hub_source = area_hub.read_text(encoding="utf-8") if area_hub.exists() else ""
    listed = sorted(re.findall(r'"url": "(https://www\.bamegirot\.com/areas/[^"]+/)"', hub_source))
    count = re.search(r'"numberOfItems": (\d+)', hub_source)
    if listed != area_urls or not count or int(count.group(1)) != len(area_urls):
        errors.append("areas/index.html: ItemList must list every area page with a matching numberOfItems")
    for path in ["/areas/", "/about/", "/en/", *[u[len(CANONICAL_URL) - 1 :] for u in area_urls]]:
        if f'href="{path}"' not in homepage:
            errors.append(f"index.html: homepage does not link to {path}")
        if path.startswith("/areas/") and path != "/areas/" and f'href="{path}"' not in hub_source:
            errors.append(f"areas/index.html: hub does not link to {path}")

    # hreflang pairs must point at each other.
    english = (ROOT / "en" / "index.html").read_text(encoding="utf-8")
    for name, source, wanted in [
        ("index.html", homepage, f'hreflang="en" href="{CANONICAL_URL}en/"'),
        ("en/index.html", english, f'hreflang="he-IL" href="{CANONICAL_URL}"'),
    ]:
        if wanted not in source or 'hreflang="x-default"' not in source:
            errors.append(f"{name}: hreflang alternates must reference each other and set x-default")


def main() -> int:
    errors: list[str] = []
    source = INDEX.read_text(encoding="utf-8")
    parser = SiteParser()
    parser.feed(source)
    head = source.split("</head>", 1)[0]

    if not re.search(r'<html\b[^>]*\blang="he"[^>]*\bdir="rtl"', source):
        errors.append('root element must retain lang="he" and dir="rtl"')
    if not re.search(r'<meta\s+charset="UTF-8"\s*/?>', head, flags=re.IGNORECASE):
        errors.append("UTF-8 charset metadata is missing")

    titles = [normalized_text(value) for value in re.findall(r"<title>(.*?)</title>", head, re.DOTALL)]
    if titles != [SEO_TITLE]:
        errors.append("homepage must have exactly the approved SEO title")

    descriptions = matching_attrs(parser, "meta", "name", "description")
    if len(descriptions) != 1 or descriptions[0].get("content") != SEO_DESCRIPTION:
        errors.append("homepage must have exactly the approved meta description")

    canonicals = matching_attrs(parser, "link", "rel", "canonical")
    if len(canonicals) != 1 or canonicals[0].get("href") != CANONICAL_URL:
        errors.append("homepage must have one self-referencing canonical")

    robots_meta = matching_attrs(parser, "meta", "name", "robots")
    if len(robots_meta) != 1 or robots_meta[0].get("content", "").lower() != "index, follow":
        errors.append('homepage robots metadata must be exactly "index, follow"')

    expected_meta = {
        ("property", "og:title"): SEO_TITLE,
        ("property", "og:description"): SEO_DESCRIPTION,
        ("property", "og:url"): CANONICAL_URL,
        ("property", "og:locale"): "he_IL",
        ("property", "og:image"): f"{CANONICAL_URL}images/cover.jpg",
        ("name", "twitter:card"): "summary_large_image",
        ("name", "twitter:title"): SEO_TITLE,
        ("name", "twitter:description"): SEO_DESCRIPTION,
        ("name", "twitter:image"): f"{CANONICAL_URL}images/cover.jpg",
    }
    for (key, name), expected in expected_meta.items():
        matches = matching_attrs(parser, "meta", key, name)
        if len(matches) != 1 or matches[0].get("content") != expected:
            errors.append(f"missing or duplicate {name} metadata")

    h1_values = [
        normalized_text(value)
        for value in re.findall(r"<h1\b[^>]*>(.*?)</h1>", source, flags=re.DOTALL)
    ]
    if h1_values != [H1]:
        errors.append("homepage must have exactly the approved H1")
    if re.search(r"<h[4-6]\b", source):
        errors.append("heading hierarchy should not skip from H3 to lower levels")
    for semantic_tag in ("header", "nav", "main", "footer", "address"):
        if len(parser.elements.get(semantic_tag, [])) != 1:
            errors.append(f"homepage must contain exactly one <{semantic_tag}> element")

    duplicate_ids = sorted(name for name, count in Counter(parser.ids).items() if count > 1)
    if duplicate_ids:
        errors.append(f"duplicate element IDs: {', '.join(duplicate_ids)}")

    missing_fragments = sorted(set(parser.fragments) - set(parser.ids))
    if missing_fragments:
        errors.append(f"links target missing IDs: {', '.join(missing_fragments)}")

    missing_assets = sorted(
        reference
        for reference in set(parser.local_assets)
        if not (ROOT / reference).is_file()
        and not (ROOT / reference / "index.html").is_file()
    )
    if missing_assets:
        errors.append(f"missing local assets: {', '.join(missing_assets)}")

    images_without_alt = [
        attrs.get("src", "<missing src>") for attrs in parser.images if "alt" not in attrs
    ]
    if images_without_alt:
        errors.append(f"images need alt attributes: {', '.join(images_without_alt)}")
    images_without_dimensions = [
        attrs.get("src", "<missing src>")
        for attrs in parser.images
        if not attrs.get("width") or not attrs.get("height")
    ]
    if images_without_dimensions:
        errors.append(
            f"images need width and height attributes: {', '.join(images_without_dimensions)}"
        )
    if parser.images:
        hero = parser.images[0]
        if hero.get("loading") == "lazy" or hero.get("fetchpriority") != "high":
            errors.append("hero image must be eager and use high fetch priority")
        below_fold_without_lazy = [
            attrs.get("src", "<missing src>")
            for attrs in parser.images[1:]
            if attrs.get("loading") != "lazy"
        ]
        if below_fold_without_lazy:
            errors.append(
                "below-the-fold images must be lazy-loaded: "
                + ", ".join(below_fold_without_lazy)
            )
    if parser.unsafe_blank_links:
        errors.append(
            'target="_blank" links need rel="noopener": '
            + ", ".join(parser.unsafe_blank_links)
        )

    if not parser.whatsapp_links:
        errors.append("no WhatsApp conversion links found")
    elif len(set(parser.whatsapp_links)) != 1:
        errors.append("WhatsApp links do not all use the same number and prefilled message")
    elif "wa.me/972523321045" not in parser.whatsapp_links[0]:
        errors.append("WhatsApp links do not use the production number 972523321045")

    structured_roots: list[dict[str, object]] = []
    for position, payload in enumerate(parser.json_ld, start=1):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            errors.append(f"JSON-LD block {position} is invalid: {exc}")
            continue
        if isinstance(parsed, dict):
            structured_roots.append(parsed)

    if len(structured_roots) != 1:
        errors.append("homepage must contain exactly one JSON-LD block")
    graph: list[dict[str, object]] = []
    if structured_roots:
        root = structured_roots[0]
        if root.get("@context") != "https://schema.org":
            errors.append("JSON-LD must use https://schema.org")
        raw_graph = root.get("@graph", [])
        if isinstance(raw_graph, list):
            graph = [item for item in raw_graph if isinstance(item, dict)]
        else:
            errors.append("JSON-LD @graph must be an array")

    def schema_types(item: dict[str, object]) -> set[str]:
        raw_type = item.get("@type")
        if isinstance(raw_type, str):
            return {raw_type}
        if isinstance(raw_type, list):
            return {value for value in raw_type if isinstance(value, str)}
        return set()

    graph_types = set().union(*(schema_types(item) for item in graph)) if graph else set()
    for required_type in ("WebSite", "ProfessionalService", "Person", "Service", "FAQPage"):
        if required_type not in graph_types:
            errors.append(f"JSON-LD graph is missing {required_type}")
    for entity in graph:
        entity_id = entity.get("@id")
        if not isinstance(entity_id, str) or not entity_id.startswith(CANONICAL_URL):
            errors.append(f"JSON-LD entity lacks a stable canonical @id: {entity.get('@type')}")

    faq_schema = next(
        (item for item in graph if "FAQPage" in schema_types(item)),
        None,
    )
    faq_matches = re.findall(
        r'<button\b[^>]*class="faq-question"[^>]*>.*?<span>(.*?)</span>.*?</button>'
        r'.*?<div\b[^>]*class="faq-answer"[^>]*>\s*<p>(.*?)</p>',
        source,
        flags=re.DOTALL,
    )
    visible_faq = [
        {"name": normalized_text(question), "text": normalized_text(answer)}
        for question, answer in faq_matches
    ]
    schema_faq = []
    if faq_schema:
        for entity in faq_schema.get("mainEntity", []):
            if isinstance(entity, dict):
                accepted = entity.get("acceptedAnswer", {})
                schema_faq.append(
                    {
                        "name": entity.get("name", ""),
                        "text": accepted.get("text", "") if isinstance(accepted, dict) else "",
                    }
                )
    else:
        errors.append("FAQPage JSON-LD is missing")
    if visible_faq != schema_faq:
        errors.append("visible FAQ content and FAQPage JSON-LD are out of sync")

    required_snippets = {
        "canonical production domain": "https://www.bamegirot.com/",
        "Google Ads account tag": "AW-10933411346",
        "Google Ads conversion label (WhatsApp)": "AW-10933411346/F_bFCM_o-J4cEJK8ut0o",
        "Google Ads conversion label (phone click)": "AW-10933411346/U4JGCLrCm9ocEJK8ut0o",
        "Open Graph fallback image": "https://www.bamegirot.com/images/cover.jpg",
        "owner full name": "ליאור בוכשטב",
        "main service area": "מתל אביב ועד חיפה",
        "visible telephone": "052-332-1045",
    }
    for label, snippet in required_snippets.items():
        if snippet not in source:
            errors.append(f"missing {label}: {snippet}")

    for verification_file in ("google2a0754c9bf168ad4.html", "google83efa163eba9ecb8.html"):
        if not (ROOT / verification_file).is_file():
            errors.append(f"missing Google verification file: {verification_file}")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    if f"Sitemap: {CANONICAL_URL}sitemap.xml" not in robots:
        errors.append("robots.txt does not point to the production sitemap")
    for user_agent in (
        "Googlebot", "Bingbot", "GPTBot", "OAI-SearchBot", "ChatGPT-User",
        "PerplexityBot", "ClaudeBot", "Claude-SearchBot", "Google-Extended",
        "Applebot-Extended",
    ):
        if f"User-agent: {user_agent}\nAllow: /" not in robots:
            errors.append(f"robots.txt does not explicitly allow {user_agent}")

    try:
        sitemap_root = ET.fromstring(sitemap)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = [
            node.text for node in sitemap_root.findall("sm:url/sm:loc", namespace)
        ]
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_sitemap  # noqa: E402

        expected_urls = [build_sitemap.url_for(page) for page in build_sitemap.pages()]
        if sitemap_urls != expected_urls:
            errors.append(
                "sitemap.xml must list the canonical homepage and every guide page: "
                + ", ".join(expected_urls)
            )
    except ET.ParseError as exc:
        errors.append(f"sitemap.xml is invalid XML: {exc}")

    # sitemap.xml, llms.txt and the visible "עודכן ב..." dates are generated from
    # each page's dateModified — build_sitemap.py owns them.
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_sitemap  # noqa: E402

    errors.extend(build_sitemap.check())

    # Judaica is not offered (standing decision, 2026-10-30) and must not be
    # claimed anywhere a visitor or a crawler can read. Same scan enforces
    # the retired not-a-buyer positioning (2026-11-19).
    for path in [
        ROOT / "llms.txt",
        ROOT / "llms-full.txt",
        *ROOT.glob("*.html"),
        *[p for folder in ("guides", "areas", "about", "en") for p in ROOT.glob(f"{folder}/**/*.html")],
    ]:
        text = path.read_text(encoding="utf-8")
        for term in JUDAICA_TERMS:
            if term in text:
                errors.append(f"{path.relative_to(ROOT)}: mentions {term} (Judaica / Jewish ritual items are not offered)")
        for term in FILLER_TERMS:
            if term in text:
                errors.append(f"{path.relative_to(ROOT)}: says {term!r} (generic personal-service filler is not wanted)")
        for term in NOT_A_BUYER_TERMS:
            if term.lower() in text.lower():
                errors.append(f"{path.relative_to(ROOT)}: says {term!r} (the not-a-buyer positioning is retired; Lior does buy items)")

    # IndexNow proves ownership by serving <key>.txt from the site root; the
    # GitHub Action finds the key by that file name.
    key_files = [p for p in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}\.txt", p.name)]
    if len(key_files) != 1:
        errors.append("expected exactly one IndexNow key file (<32 hex chars>.txt) at the repo root")
    elif key_files[0].read_text(encoding="utf-8").strip() != key_files[0].stem:
        errors.append(f"{key_files[0].name} must contain its own file name as the key")

    try:
        vercel_config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        if vercel_config.get("trailingSlash") is not True:
            errors.append("vercel.json must enforce trailing slashes")
        redirects = vercel_config.get("redirects", [])
        redirect_hosts = {
            condition.get("value")
            for redirect in redirects
            if isinstance(redirect, dict)
            for condition in redirect.get("has", [])
            if isinstance(condition, dict) and condition.get("type") == "host"
        }
        for host in ("bamegirot.com", "mom-antiques.vercel.app"):
            if host not in redirect_hosts:
                errors.append(f"vercel.json does not canonicalize host {host}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"vercel.json is missing or invalid: {exc}")

    check_javascript(parser.inline_js, errors)
    check_guides(errors, source)

    if errors:
        print("site checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "site checks passed "
        f"({len(parser.local_assets)} local references, "
        f"{len(graph)} JSON-LD entities, "
        f"{len(visible_faq)} FAQs, "
        f"{len(parser.inline_js)} inline JavaScript blocks)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
