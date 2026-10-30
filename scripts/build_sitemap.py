#!/usr/bin/env python3
"""Build sitemap.xml from the pages themselves, so lastmod is never hand-edited.

Source of truth for a page's date is the ``dateModified`` of its main JSON-LD
entity (Article / CollectionPage / WebSite). From it this script derives:

  * the <lastmod> of that page in sitemap.xml;
  * the visible "עודכן ב<חודש> <שנה>" <time> in the page byline (guides + hub);
  * the "עודכן לאחרונה" line in llms.txt (newest page date).

Images listed under each sitemap URL are the gallery photos the page itself
shows (images/item-NN.webp), in document order.

Usage
  python3 scripts/build_sitemap.py                 # rewrite sitemap/llms/time tags
  python3 scripts/build_sitemap.py --touch PAGE…   # set dateModified = today, then rewrite
  python3 scripts/build_sitemap.py --check         # exit 1 if anything is out of date

``--check`` is what scripts/check_site.py runs. Besides comparing the generated
output with what is committed, it refuses a page that has uncommitted edits
but whose dateModified is not today — edit a page, touch it, then commit.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE = "https://www.bamegirot.com/"
HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
    7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}
MAIN_TYPES = ("Article", "CollectionPage", "WebSite")
DATE_RE = re.compile(r'"dateModified": "(\d{4}-\d{2}-\d{2})"')
TIME_RE = re.compile(r'<time datetime="\d{4}-\d{2}-\d{2}">[^<]*</time>')
IMG_RE = re.compile(r'<img[^>]*\ssrc="/?(images/item-\d+\.webp)"')
LLMS_RE = re.compile(r"^(- )?עודכן לאחרונה: \d{4}-\d{2}-\d{2}$", re.M)


def pages() -> list[pathlib.Path]:
    return (
        [ROOT / "index.html", ROOT / "guides" / "index.html"]
        + sorted(ROOT.glob("guides/*/index.html"))
        + sorted(ROOT.glob("events/*/index.html"))
    )


def url_for(page: pathlib.Path) -> str:
    rel = page.relative_to(ROOT).parent.as_posix()
    return BASE if rel == "." else f"{BASE}{rel}/"


def date_of(source: str, page: pathlib.Path) -> str:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', source, re.S)
    graph = json.loads(match.group(1))["@graph"]
    for wanted in MAIN_TYPES:
        for item in graph:
            if item.get("@type") == wanted and item.get("dateModified"):
                return item["dateModified"]
    raise SystemExit(f"{page}: no main entity with dateModified")


def visible_label(date: str) -> str:
    d = dt.date.fromisoformat(date)
    return f'<time datetime="{date}">עודכן ב{HEBREW_MONTHS[d.month]} {d.year}</time>'


def synced_page(source: str, date: str) -> str:
    """Return the page with its visible <time> matching ``date`` (no-op if none)."""
    return TIME_RE.sub(visible_label(date), source, count=1)


def render_sitemap(entries: list[tuple[str, str, list[str]]]) -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    for url, date, images in entries:
        out += ["  <url>", f"    <loc>{url}</loc>", f"    <lastmod>{date}</lastmod>"]
        for image in images:
            out += ["    <image:image>", f"      <image:loc>{BASE}{image}</image:loc>", "    </image:image>"]
        out.append("  </url>")
    out.append("</urlset>")
    return "\n".join(out) + "\n"


def build() -> tuple[str, str, dict[pathlib.Path, str]]:
    """Return (sitemap.xml, llms.txt, {page: synced source}) as they should be."""
    entries, synced = [], {}
    for page in pages():
        source = page.read_text(encoding="utf-8")
        date = date_of(source, page)
        images = list(dict.fromkeys(IMG_RE.findall(source)))
        entries.append((url_for(page), date, images))
        synced[page] = synced_page(source, date)
    newest = max(date for _, date, _ in entries)
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    if not LLMS_RE.search(llms):
        raise SystemExit("llms.txt is missing its 'עודכן לאחרונה: YYYY-MM-DD' line")
    llms = LLMS_RE.sub(lambda m: f"{m.group(1) or ''}עודכן לאחרונה: {newest}", llms)
    return render_sitemap(entries), llms, synced


def touch(targets: list[str]) -> None:
    today = dt.date.today().isoformat()
    for target in targets:
        page = (ROOT / target).resolve()
        if page.is_dir():
            page = page / "index.html"
        source = page.read_text(encoding="utf-8")
        if len(DATE_RE.findall(source)) != 1:
            raise SystemExit(f"{page}: expected exactly one dateModified")
        page.write_text(DATE_RE.sub(f'"dateModified": "{today}"', source), encoding="utf-8")
        print(f"touched {page.relative_to(ROOT)} -> {today}")


def dirty_pages() -> list[pathlib.Path]:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", *[str(p.relative_to(ROOT)) for p in pages()]],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [ROOT / line[3:].strip() for line in out.splitlines() if line.strip()]


def only_time_tag_changed(page: pathlib.Path, source: str, date: str) -> bool:
    """True when the working copy differs from HEAD only by the synced <time>."""
    try:
        head = subprocess.run(
            ["git", "show", f"HEAD:{page.relative_to(ROOT).as_posix()}"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return False
    return synced_page(head, date) == source


def check() -> list[str]:
    errors = []
    sitemap, llms, synced = build()
    if (ROOT / "sitemap.xml").read_text(encoding="utf-8") != sitemap:
        errors.append("sitemap.xml is stale — run: python3 scripts/build_sitemap.py")
    if (ROOT / "llms.txt").read_text(encoding="utf-8") != llms:
        errors.append("llms.txt 'עודכן לאחרונה' is stale — run: python3 scripts/build_sitemap.py")
    for page, source in synced.items():
        if page.read_text(encoding="utf-8") != source:
            errors.append(f"{page.relative_to(ROOT)}: visible <time> does not match dateModified — run: python3 scripts/build_sitemap.py")
    today = dt.date.today().isoformat()
    for page in dirty_pages():
        source = page.read_text(encoding="utf-8")
        date = date_of(source, page)
        if date != today and not only_time_tag_changed(page, source, date):
            rel = page.relative_to(ROOT)
            errors.append(f"{rel} has uncommitted edits but dateModified is {date} — run: python3 scripts/build_sitemap.py --touch {rel}")
    return errors


def main(argv: list[str]) -> int:
    if argv[:1] == ["--check"]:
        errors = check()
        for error in errors:
            print(error)
        return 1 if errors else 0
    if argv[:1] == ["--touch"]:
        touch(argv[1:])
    sitemap, llms, synced = build()
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (ROOT / "llms.txt").write_text(llms, encoding="utf-8")
    for page, source in synced.items():
        if page.read_text(encoding="utf-8") != source:
            page.write_text(source, encoding="utf-8")
    print(f"sitemap.xml written: {len(pages())} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
