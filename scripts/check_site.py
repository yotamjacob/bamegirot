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
SEO_TITLE = "הערכת תכולת דירה ועזבונות | מכירת עתיקות ופריטי וינטג׳ - במגירות"
SEO_DESCRIPTION = (
    "הערכת תכולת דירה ועזבונות, זיהוי עתיקות וליווי במכירת ציורים, יודאיקה, "
    "כלי כסף, קרמיקה ורהיטי וינטג׳ - בשירות אישי וללא התחייבות."
)
H1 = "הערכת תכולת דירה ועזבונות וליווי במכירת עתיקות ופריטי וינטג׳"


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
        # Guards the same positioning as before — the buyer is a third party,
        # so the appraisal is independent — but stated forwards. Copy here
        # leads with what Lior does, never with what she is not.
        "independent-appraisal positioning": "הפריטים נמכרים לקונים בשוק, כך שההערכה נשארת עצמאית.",
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
    for user_agent in ("Googlebot", "Bingbot", "OAI-SearchBot", "PerplexityBot"):
        if f"User-agent: {user_agent}\nAllow: /" not in robots:
            errors.append(f"robots.txt does not explicitly allow {user_agent}")

    try:
        sitemap_root = ET.fromstring(sitemap)
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_urls = [
            node.text for node in sitemap_root.findall("sm:url/sm:loc", namespace)
        ]
        expected_urls = [CANONICAL_URL, f"{CANONICAL_URL}guides/"] + [
            f"{CANONICAL_URL}{page.parent.relative_to(ROOT)}/"
            for page in sorted(ROOT.glob("guides/*/index.html"))
        ]
        if sitemap_urls != expected_urls:
            errors.append(
                "sitemap.xml must list the canonical homepage and every guide page: "
                + ", ".join(expected_urls)
            )
    except ET.ParseError as exc:
        errors.append(f"sitemap.xml is invalid XML: {exc}")

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
