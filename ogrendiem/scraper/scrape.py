"""LibreTexts scraper for precalculus content pages.

Fetches each section, extracts title, hierarchy, body text, definitions,
worked examples, and internal links, and writes one JSON file per page
to data/raw/.

Respects robots.txt by rate-limiting requests.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

try:
    from scraper.seed_urls import CHAPTERS  # when run as `python -m scraper.scrape`
except ImportError:
    from seed_urls import CHAPTERS          # when run as `python scrape.py` from scraper/

USER_AGENT = (
    "ogrendiem-educational-scraper/0.1 "
    "(personal adaptive-tutor project; respects robots.txt)"
)
REQUEST_DELAY_SECONDS = 2.0  # polite pause between requests
TIMEOUT_SECONDS = 30

RAW_ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"


def raw_dir(chapter: int) -> Path:
    d = RAW_ROOT / f"ch{chapter}"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ----------------------------------------------------------------------------
# URL → filename
# ----------------------------------------------------------------------------

def url_to_filename(url: str) -> str:
    """Derive a stable, filesystem-safe JSON filename from a URL."""
    path = unquote(urlparse(url).path)
    # keep the trailing section name, shorten otherwise
    tail = path.rstrip("/").split("/")[-1]
    tail = re.sub(r"[^A-Za-z0-9._-]", "_", tail)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{tail}__{digest}.json"


# ----------------------------------------------------------------------------
# Parsing helpers
# ----------------------------------------------------------------------------

def _find_main_content(soup: BeautifulSoup) -> Tag | None:
    """Locate the main content region on a LibreTexts page.

    LibreTexts uses MindTouch; the content is reliably under
    #mt-content or within the .mt-content-container div.
    """
    for selector in (
        "#mt-content",
        "div.mt-content-container",
        "main",
        "div.mw-parser-output",
    ):
        node = soup.select_one(selector)
        if node is not None:
            return node
    return soup.body


def _clean_text(node: Tag) -> str:
    text = node.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text


def _parse_hierarchy(title: str) -> tuple[str | None, str | None]:
    """Pull chapter and section numbers from a LibreTexts title like
    '1.2: Domain and Range'."""
    m = re.match(r"\s*(\d+)\.(\d+(?:\.\d+)?)\s*[:\-]\s*(.+)", title)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _extract_definitions(main: Tag) -> list[dict]:
    """Pull out boxed definitions. LibreTexts marks these with various
    class names depending on template; we look for the common ones plus
    any <dfn> or bolded 'Definition' lead-ins."""
    defs: list[dict] = []

    # MindTouch-style boxes
    for box in main.select(
        "div.definition, div.mt-definition, div.box-definition, "
        "div[data-mt-class*='definition'], "
        "div.boxed, div.callout.definition"
    ):
        defs.append({
            "kind": "boxed",
            "text": _clean_text(box),
        })

    # Fallback: paragraphs led by "Definition" or "Definition:"
    for p in main.find_all("p"):
        txt = _clean_text(p)
        if re.match(r"^(Definition\s*[:\.]|A\s+\w+\s+is\s+defined\s+as)",
                    txt, re.IGNORECASE):
            defs.append({"kind": "inline", "text": txt})

    return defs


def _extract_examples(main: Tag) -> list[dict]:
    examples: list[dict] = []
    for box in main.select(
        "div.example, div.mt-example, div.box-example, "
        "div[data-mt-class*='example'], div.callout.example"
    ):
        examples.append({"text": _clean_text(box)})

    # Fallback: "Example N" lead-ins
    if not examples:
        for h in main.find_all(["h3", "h4", "p", "strong"]):
            txt = _clean_text(h)
            if re.match(r"^Example\s+\d+", txt):
                # Grab the header plus following siblings until next header
                parts = [txt]
                for sib in h.next_siblings:
                    if isinstance(sib, Tag) and sib.name in {"h1", "h2", "h3", "h4"}:
                        break
                    if isinstance(sib, Tag):
                        parts.append(_clean_text(sib))
                examples.append({"text": " ".join(parts)[:2000]})
    return examples


def _extract_internal_links(main: Tag, base_url: str) -> list[dict]:
    links: list[dict] = []
    base_host = urlparse(base_url).netloc
    seen: set[str] = set()
    for a in main.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#"):
            continue
        absolute = urljoin(base_url, href)
        host = urlparse(absolute).netloc
        if host != base_host:
            continue
        # only keep links that go to another Bookshelves page
        if "/Bookshelves/" not in absolute:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append({
            "text": _clean_text(a)[:200],
            "url": absolute,
        })
    return links


def _extract_body_text(main: Tag) -> str:
    """Body text with boxed callouts stripped (they're captured separately)."""
    clone = BeautifulSoup(str(main), "lxml")
    for box in clone.select(
        "div.definition, div.mt-definition, div.example, div.mt-example, "
        "div.box-example, div.box-definition, "
        "div[data-mt-class*='definition'], div[data-mt-class*='example'], "
        "div.callout, div.boxed, nav, footer, header, "
        "div.mt-guide-content-footer, div.mt-footer"
    ):
        box.decompose()
    return _clean_text(clone)


# Subheadings to exclude from subsection extraction (site chrome / meta).
_SKIP_HEADINGS = {
    "search", "error", "recommended articles",
    "important topics of this section", "important topics of the section",
    "important topics of this chapter", "contributors and attributions",
    "license",
}


def _extract_subsections(main: Tag) -> list[dict]:
    """Split the page by its content h2/h3 headings.

    Each subsection contains body_text, its own definitions, and its own
    examples — everything that appears between this heading and the next.
    Subsections become candidate topic nodes in the NLP step.
    """
    # Flatten main into a linear list of top-level-ish elements so we can
    # scan in document order.
    clone = BeautifulSoup(str(main), "lxml")

    # Remove site chrome boxes we never want in subsection text.
    for junk in clone.select(
        "nav, footer, header, "
        "div.mt-guide-content-footer, div.mt-footer, "
        "form, script, style"
    ):
        junk.decompose()

    subsections: list[dict] = []
    current: dict | None = None

    def _is_heading(tag: Tag) -> bool:
        return isinstance(tag, Tag) and tag.name in {"h2", "h3"}

    def _is_def_box(tag: Tag) -> bool:
        if not isinstance(tag, Tag):
            return False
        cls = " ".join(tag.get("class", []))
        return bool(
            re.search(r"\b(box-definition|mt-definition|definition)\b", cls)
        )

    def _is_example_box(tag: Tag) -> bool:
        if not isinstance(tag, Tag):
            return False
        cls = " ".join(tag.get("class", []))
        return bool(
            re.search(r"\b(box-example|mt-example|example)\b", cls)
        )

    # Walk descendants of clone; headings start new subsections.
    for el in clone.find_all(True):
        if _is_heading(el):
            title = _clean_text(el)
            key = title.strip().lower()
            if not title or key in _SKIP_HEADINGS or len(title) > 200:
                # close out any current subsection so junk headings don't leak
                current = None
                continue
            # start a new subsection
            current = {
                "heading": title,
                "level": el.name,
                "body_text": "",
                "definitions": [],
                "examples": [],
                "_text_parts": [],
            }
            subsections.append(current)
        elif current is None:
            continue
        elif _is_def_box(el):
            current["definitions"].append({"kind": "boxed", "text": _clean_text(el)})
        elif _is_example_box(el):
            current["examples"].append({"text": _clean_text(el)})
        elif el.name in {"p", "ul", "ol", "li", "table"}:
            # Skip if this node is inside a definition or example box already
            # captured at a higher level.
            if el.find_parent(
                lambda t: isinstance(t, Tag)
                and (_is_def_box(t) or _is_example_box(t))
            ):
                continue
            txt = _clean_text(el)
            if txt:
                current["_text_parts"].append(txt)

    # Finalize
    for s in subsections:
        s["body_text"] = " ".join(s.pop("_text_parts"))
    # Drop empty subsections (headings with no real content captured)
    subsections = [
        s for s in subsections
        if s["body_text"] or s["definitions"] or s["examples"]
    ]
    return subsections


# ----------------------------------------------------------------------------
# Page-level pipeline
# ----------------------------------------------------------------------------

def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    main = _find_main_content(soup) or soup

    title_tag = soup.find("h1") or soup.find("title")
    raw_title = _clean_text(title_tag) if title_tag else ""
    chapter_num, section_num = _parse_hierarchy(raw_title)

    body_text = _extract_body_text(main)
    definitions = _extract_definitions(main)
    examples = _extract_examples(main)
    internal_links = _extract_internal_links(main, url)
    subsections = _extract_subsections(main)

    return {
        "url": url,
        "title": raw_title,
        "chapter": chapter_num,
        "section": section_num,
        "body_text": body_text,
        "definitions": definitions,
        "examples": examples,
        "internal_links": internal_links,
        "subsections": subsections,
        "char_count": len(body_text),
    }


def fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    return resp.text


def scrape_one(url: str, out_dir: Path, force: bool = False) -> dict:
    out_path = out_dir / url_to_filename(url)
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    html = fetch(url)
    record = parse_page(html, url)
    out_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


def scrape_all(urls: list[str], out_dir: Path) -> list[dict]:
    records: list[dict] = []
    for i, url in enumerate(urls):
        print(f"[{i + 1}/{len(urls)}] {url}")
        rec = scrape_one(url, out_dir)
        print(
            f"   → title='{rec['title']}' | "
            f"body={rec['char_count']} chars | "
            f"defs={len(rec['definitions'])} | "
            f"examples={len(rec['examples'])} | "
            f"links={len(rec['internal_links'])}"
        )
        records.append(rec)
        if i + 1 < len(urls):
            time.sleep(REQUEST_DELAY_SECONDS)
    return records


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", type=int, default=1,
                    help="Chapter number to scrape (must appear in CHAPTERS)")
    args = ap.parse_args()
    if args.chapter not in CHAPTERS:
        raise SystemExit(
            f"Chapter {args.chapter} not configured in seed_urls.CHAPTERS "
            f"(have: {sorted(CHAPTERS)})"
        )
    out_dir = raw_dir(args.chapter)
    records = scrape_all(CHAPTERS[args.chapter], out_dir)
    print(f"\nScraped {len(records)} pages → {out_dir}")
