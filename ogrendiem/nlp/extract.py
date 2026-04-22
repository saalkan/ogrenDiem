"""Extract topics, concepts, and prerequisite edges from scraped pages.

Reads  data/raw/*.json  (produced by scraper.scrape) and writes
  data/processed/topics.json  with fields: topics[], edges[], meta.

Pipeline
--------
1.  Build a flat list of *topics* from each scraped page. Prefer h2/h3
    subsections; fall back to section-level when a page has no
    content-bearing subheadings.
2.  For each topic, extract
        - defined terms (from the captured "Definition" boxes),
        - key concepts (TF-IDF top terms across all topics),
        - a 1-to-5 difficulty estimate based on content signals.
3.  Propose prerequisite edges from four signals, each tagged with its
    source so downstream stages can weigh them independently:
        · term-definition   — topic B uses a term defined in topic A
        · explicit-ref      — B's text contains "Section X.Y" pointing at A
        · structural-sec    — A is the preceding subsection within a section
        · structural-chap   — A is the last topic of the preceding section
4.  Deduplicate edges, pick the strongest source when multiple fire on the
    same edge, and drop self-loops.

All outputs are JSON-serialisable.
"""
from __future__ import annotations

import glob
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = ROOT / "data" / "raw"
PROCESSED_ROOT = ROOT / "data" / "processed"


def raw_dir(chapter: int) -> Path:
    return RAW_ROOT / f"ch{chapter}"


def processed_dir(scope: str) -> Path:
    """scope is e.g. 'ch1' for a single chapter or 'g1-2-3-4' for a group."""
    d = PROCESSED_ROOT / scope
    d.mkdir(parents=True, exist_ok=True)
    return d

# ----------------------------------------------------------------------------
# Topic construction
# ----------------------------------------------------------------------------

def _short_section_title(full_title: str) -> str:
    """'1.2: Domain and Range' → 'Domain and Range'."""
    parts = full_title.split(":", 1)
    return parts[1].strip() if len(parts) == 2 else full_title.strip()


def build_topics(records: list[dict], chapter: int) -> list[dict]:
    topics: list[dict] = []
    for rec in records:
        section_num = rec.get("section") or "0"
        short = _short_section_title(rec.get("title", ""))
        subs = rec.get("subsections", []) or []
        if len(subs) >= 2:
            for i, sub in enumerate(subs):
                topics.append({
                    "topic_id": f"ch{chapter}_s{section_num}_t{i + 1}",
                    "title": sub["heading"],
                    "parent_section": short,
                    "parent_chapter_num": str(chapter),
                    "parent_section_num": str(section_num),
                    "position_in_section": i,
                    "body_text": sub["body_text"],
                    "definitions": sub["definitions"],
                    "examples": sub["examples"],
                    "source_url": rec["url"],
                })
        else:
            merged_body_parts = [rec.get("body_text", "")]
            merged_defs = list(rec.get("definitions", []))
            merged_examples = list(rec.get("examples", []))
            for sub in subs:
                merged_body_parts.append(sub.get("body_text", ""))
                merged_defs.extend(sub.get("definitions", []))
                merged_examples.extend(sub.get("examples", []))
            topics.append({
                "topic_id": f"ch{chapter}_s{section_num}_t1",
                "title": short,
                "parent_section": short,
                "parent_chapter_num": str(chapter),
                "parent_section_num": str(section_num),
                "position_in_section": 0,
                "body_text": " ".join(p for p in merged_body_parts if p),
                "definitions": merged_defs,
                "examples": merged_examples,
                "source_url": rec["url"],
            })
    return topics


# ----------------------------------------------------------------------------
# Concept / defined-term extraction
# ----------------------------------------------------------------------------

# Common non-content tokens that sneak in from LaTeX artifacts
_NOISE = {
    "pageindex", "displaystyle", "left", "right", "quad", "therefore",
    "text", "frac", "sqrt", "begin", "end", "array", "cdot",
}


def _normalize(term: str) -> str:
    t = term.strip().lower()
    t = re.sub(r"\s+", " ", t)
    # strip leading/trailing punctuation
    t = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", t)
    return t


_DEF_HEAD_RE = re.compile(
    r"^\s*Definition[s]?\s*[:\-–]?\s*(?P<term>[A-Z][A-Za-z0-9 \-\/]{1,60}?)"
    r"(?=[\.\:\n]|\s+[A-Z]|\s+is\b|\s+are\b|$)",
    re.IGNORECASE,
)
_IS_DEFINED_RE = re.compile(
    r"\b(?:a|an|the)\s+(?P<term>[a-z][a-z\- ]{1,40}?)\s+is\s+(?:defined\s+as|"
    r"a\s+[a-z][a-z\- ]{1,40}?\s+that|called)\b",
    re.IGNORECASE,
)


def extract_defined_terms(topic: dict) -> list[str]:
    """Pull the defined term(s) out of a topic's definition boxes."""
    terms: list[str] = []
    for d in topic.get("definitions", []):
        text = d.get("text", "")
        m = _DEF_HEAD_RE.match(text)
        if m:
            terms.append(_normalize(m.group("term")))
            continue
        m2 = _IS_DEFINED_RE.search(text[:200])
        if m2:
            terms.append(_normalize(m2.group("term")))
    # dedupe, drop junk
    seen: set[str] = set()
    clean: list[str] = []
    for t in terms:
        if not t or len(t) < 3 or t in _NOISE:
            continue
        if t in seen:
            continue
        seen.add(t)
        clean.append(t)
    return clean


def tfidf_key_concepts(topics: list[dict], top_k: int = 6) -> dict[str, list[str]]:
    """Return {topic_id: [top terms]} using TF-IDF over the corpus."""
    docs = [t.get("body_text", "") or t.get("title", "") for t in topics]
    vec = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
        min_df=1,
        max_df=0.85,
        token_pattern=r"(?u)\b[A-Za-z][A-Za-z\-]{2,}\b",
    )
    X = vec.fit_transform(docs)
    vocab = vec.get_feature_names_out()
    out: dict[str, list[str]] = {}
    for i, topic in enumerate(topics):
        row = X.getrow(i).toarray().ravel()
        top_idx = row.argsort()[::-1][: top_k * 3]  # oversample, filter noise
        picks: list[str] = []
        for j in top_idx:
            if row[j] <= 0:
                break
            term = vocab[j]
            norm = _normalize(term)
            if not norm or norm in _NOISE:
                continue
            picks.append(term)
            if len(picks) >= top_k:
                break
        out[topic["topic_id"]] = picks
    return out


# ----------------------------------------------------------------------------
# Difficulty
# ----------------------------------------------------------------------------

def estimate_difficulty(topic: dict, max_section: int) -> int:
    """Integer 1..5 heuristic.

    Signals combined:
      · position in chapter  (later sections → harder baseline)
      · body length          (longer → harder)
      · definition count     (more new terms → harder)
      · notation density     (more LaTeX → harder)
    """
    try:
        sec = float(topic["parent_section_num"])
    except (TypeError, ValueError):
        sec = 1.0
    # Map section position within the chapter to a 1..4 baseline.
    base = 1 + 3 * (sec - 1) / max(max_section - 1, 1)

    body = topic.get("body_text", "")
    body_len = len(body)
    n_defs = len(topic.get("definitions", []))
    notation_hits = body.count("\\(") + body.count("\\[")
    notation_density = notation_hits / max(body_len / 1000, 1e-3)  # per 1k chars

    bump = 0.0
    if body_len > 2500:
        bump += 0.3
    if n_defs >= 3:
        bump += 0.3
    if notation_density > 6:
        bump += 0.4

    score = base + bump
    return max(1, min(5, int(round(score))))


def difficulty_tier(level: int) -> str:
    if level <= 2:
        return "easy"
    if level == 3:
        return "medium"
    return "hard"


# ----------------------------------------------------------------------------
# Prerequisite edges
# ----------------------------------------------------------------------------

# Rank of edge sources — higher = stronger, used to pick winner on dedupe.
_SOURCE_RANK = {
    "term-definition": 4,
    "explicit-ref": 3,
    "structural-sec": 2,
    "structural-chap": 1,
}


def _section_key(topic: dict) -> tuple:
    try:
        ch = int(topic.get("parent_chapter_num", 0))
    except (TypeError, ValueError):
        ch = 0
    try:
        parts = tuple(int(x) for x in str(topic["parent_section_num"]).split("."))
    except (TypeError, ValueError):
        parts = (0,)
    return (ch, parts, topic.get("position_in_section", 0))


def _sec_key_only(topic: dict) -> tuple:
    """(chapter, section_parts) — the section-level part of _section_key."""
    return _section_key(topic)[:2]


def edges_from_defined_terms(topics: list[dict]) -> list[dict]:
    """If topic B's body contains a term first defined in topic A, A→B."""
    defs_by_term: dict[str, str] = {}  # term → source topic_id
    for t in topics:
        for term in extract_defined_terms(t):
            # Keep the earliest defining topic (by section order)
            if term not in defs_by_term:
                defs_by_term[term] = t["topic_id"]
            else:
                # Prefer earlier in chapter
                existing = next(x for x in topics if x["topic_id"] == defs_by_term[term])
                if _section_key(t) < _section_key(existing):
                    defs_by_term[term] = t["topic_id"]

    by_id = {t["topic_id"]: t for t in topics}
    edges: list[dict] = []
    for b in topics:
        body_lc = b.get("body_text", "").lower()
        title_lc = b.get("title", "").lower()
        hay = f"{title_lc} {body_lc}"
        for term, src_id in defs_by_term.items():
            if src_id == b["topic_id"]:
                continue
            # Term-definition edges must flow in chapter order — the
            # defining topic must come *before* the topic that uses the term.
            # Otherwise a word that happens to be defined in a later section
            # (e.g. "vertical" in 1.5 Transformations) would spuriously be
            # marked as prerequisite to an earlier topic that uses the same
            # word with a different meaning (e.g. 1.1 "vertical line test").
            if _section_key(by_id[src_id]) >= _section_key(b):
                continue
            if re.search(rf"\b{re.escape(term)}\b", hay):
                edges.append({
                    "from": src_id,
                    "to": b["topic_id"],
                    "source": "term-definition",
                    "evidence": term,
                })
    return edges


_REF_RE = re.compile(r"[Ss]ection\s+(\d+)\.(\d+)")


def edges_from_explicit_refs(topics: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in topics:
        by_key[(str(t["parent_chapter_num"]), str(t["parent_section_num"]))].append(t)

    edges: list[dict] = []
    for b in topics:
        body = b.get("body_text", "")
        for m in _REF_RE.finditer(body):
            ch, sec = m.group(1), m.group(2)
            if ch == str(b["parent_chapter_num"]) and sec == str(b["parent_section_num"]):
                continue
            for a in by_key.get((ch, sec), []):
                edges.append({
                    "from": a["topic_id"],
                    "to": b["topic_id"],
                    "source": "explicit-ref",
                    "evidence": f"Section {ch}.{sec}",
                })
    return edges


def edges_structural_within_section(topics: list[dict]) -> list[dict]:
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for t in topics:
        by_key[_sec_key_only(t)].append(t)
    edges: list[dict] = []
    for key, group in by_key.items():
        group_sorted = sorted(group, key=lambda t: t["position_in_section"])
        for a, b in zip(group_sorted, group_sorted[1:]):
            edges.append({
                "from": a["topic_id"],
                "to": b["topic_id"],
                "source": "structural-sec",
                "evidence": (
                    f"adjacent in section "
                    f"{a['parent_chapter_num']}.{a['parent_section_num']}"
                ),
            })
    return edges


def edges_structural_across_sections(topics: list[dict]) -> list[dict]:
    by_key: dict[tuple, list[dict]] = defaultdict(list)
    for t in topics:
        by_key[_sec_key_only(t)].append(t)
    keys_sorted = sorted(by_key.keys())
    edges: list[dict] = []
    for prev_key, next_key in zip(keys_sorted, keys_sorted[1:]):
        prev_last = sorted(
            by_key[prev_key], key=lambda t: t["position_in_section"]
        )[-1]
        next_first = sorted(
            by_key[next_key], key=lambda t: t["position_in_section"]
        )[0]
        edges.append({
            "from": prev_last["topic_id"],
            "to": next_first["topic_id"],
            "source": "structural-chap",
            "evidence": (
                f"section {prev_last['parent_chapter_num']}.{prev_last['parent_section_num']}"
                f" → {next_first['parent_chapter_num']}.{next_first['parent_section_num']}"
            ),
        })
    return edges


def dedupe_edges(edges: Iterable[dict]) -> list[dict]:
    """Pick the single strongest edge per (from, to) pair; drop self-loops."""
    best: dict[tuple[str, str], dict] = {}
    for e in edges:
        if e["from"] == e["to"]:
            continue
        key = (e["from"], e["to"])
        prev = best.get(key)
        if prev is None or _SOURCE_RANK[e["source"]] > _SOURCE_RANK[prev["source"]]:
            best[key] = e
    return list(best.values())


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def load_raw(chapter: int) -> list[dict]:
    records: list[dict] = []
    for path in sorted(glob.glob(str(raw_dir(chapter) / "*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            records.append(json.load(f))
    # keep in chapter/section order
    records.sort(key=lambda r: [
        int(x) for x in str(r.get("section") or "0").split(".") if x.isdigit()
    ] or [0])
    return records


def run(chapters: list[int], scope: str | None = None) -> dict:
    """Build topics + edges for one or more chapters and write
    data/processed/{scope}/topics.json.
    """
    if not chapters:
        raise ValueError("chapters must be a non-empty list")
    if scope is None:
        scope = f"ch{chapters[0]}" if len(chapters) == 1 else (
            "g" + "-".join(str(c) for c in chapters)
        )

    topics: list[dict] = []
    max_sec_by_ch: dict[str, int] = {}
    for ch in chapters:
        records = load_raw(ch)
        if not records:
            raise SystemExit(
                f"No raw pages found in {raw_dir(ch)} — "
                f"run `python -m scraper.scrape --chapter {ch}` first."
            )
        ch_topics = build_topics(records, ch)
        topics.extend(ch_topics)
        mx = 1
        for t in ch_topics:
            try:
                mx = max(mx, int(float(t["parent_section_num"])))
            except (TypeError, ValueError):
                pass
        max_sec_by_ch[str(ch)] = mx

    # Key concepts via TF-IDF
    kc = tfidf_key_concepts(topics, top_k=6)

    # Annotate topics
    for t in topics:
        defined = extract_defined_terms(t)
        max_sec = max_sec_by_ch.get(str(t["parent_chapter_num"]), 1)
        level = estimate_difficulty(t, max_sec)
        t["defined_terms"] = defined
        t["concepts"] = sorted(set(defined + kc.get(t["topic_id"], [])))
        t["difficulty_level"] = level
        t["difficulty_tier"] = difficulty_tier(level)
        t["description"] = _short_description(t)
        # A 2k-char snippet used later as LLM context for question generation
        t["sample_content"] = (t.get("body_text", "") or "")[:2000]

    # Edges
    raw_edges = (
        edges_from_defined_terms(topics)
        + edges_from_explicit_refs(topics)
        + edges_structural_within_section(topics)
        + edges_structural_across_sections(topics)
    )
    edges = dedupe_edges(raw_edges)

    ch_label = (
        f"Chapter {chapters[0]}"
        if len(chapters) == 1
        else "Chapters " + ", ".join(str(c) for c in chapters)
    )
    out = {
        "meta": {
            "source": f"Lippman & Rasmussen — Precalculus, {ch_label} (LibreTexts)",
            "scope": scope,
            "chapters": list(chapters),
            "n_topics": len(topics),
            "n_edges": len(edges),
            "edge_source_counts": _counts([e["source"] for e in edges]),
        },
        "topics": topics,
        "edges": edges,
    }
    out_path = processed_dir(scope) / "topics.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"  topics: {out['meta']['n_topics']}")
    print(f"  edges : {out['meta']['n_edges']}  {out['meta']['edge_source_counts']}")
    return out


def _short_description(topic: dict) -> str:
    body = topic.get("body_text", "").strip()
    if not body:
        return topic.get("title", "")
    # First sentence or two, capped
    sents = re.split(r"(?<=[.!?])\s+", body)
    desc = " ".join(sents[:2]).strip()
    return desc[:280]


def _counts(xs: Iterable[str]) -> dict[str, int]:
    c: dict[str, int] = {}
    for x in xs:
        c[x] = c.get(x, 0) + 1
    return c


if __name__ == "__main__":
    import argparse
    try:
        from scraper.seed_urls import chapters_for, scope_label
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT / "scraper"))
        from seed_urls import chapters_for, scope_label

    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--chapter", type=int, help="single chapter number")
    group.add_argument("--group", type=str, help="group label like '1-2-3-4'")
    args = ap.parse_args()
    if args.group is not None:
        chapters = chapters_for(args.group)
    elif args.chapter is not None:
        chapters = [args.chapter]
    else:
        chapters = [1]
    run(chapters, scope=scope_label(chapters))
