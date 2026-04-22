"""Export the finalised NetworkX DAG into a Kùzu graph database.

Schema
------
NODE TABLE Topic(
    topic_id STRING PRIMARY KEY,
    title STRING,
    description STRING,
    parent_section STRING,
    parent_section_num STRING,
    position_in_section INT64,
    difficulty_level INT64,
    difficulty_tier STRING,
    depth INT64,
    source_url STRING,
    concepts STRING[],
    sample_content STRING,
)

REL TABLE REQUIRES(
    FROM Topic TO Topic,
    strength DOUBLE,
    source STRING,
    evidence STRING,
)

Idempotent: drops and recreates the database on each run for the slice.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import kuzu

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ROOT = ROOT / "data" / "processed"


def processed_for(chapter: int) -> Path:
    return PROCESSED_ROOT / f"ch{chapter}"


def db_path_for(chapter: int) -> Path:
    return ROOT / f"precalc_db_ch{chapter}"


def _list_to_kuzu_str_array(xs: list[str]) -> list[str]:
    """Kùzu accepts Python lists directly via the parameterised API."""
    return [str(x) for x in xs]


def run(chapter: int = 1) -> None:
    db_path = db_path_for(chapter)
    # Kùzu may create the DB as either a directory or a single file
    # (plus a sibling .wal) depending on version. Handle both.
    if db_path.exists():
        if db_path.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path.unlink()
    wal = db_path.with_suffix(db_path.suffix + ".wal")
    if wal.exists():
        wal.unlink()

    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    conn.execute(
        """
        CREATE NODE TABLE Topic(
            topic_id STRING,
            title STRING,
            description STRING,
            parent_section STRING,
            parent_section_num STRING,
            position_in_section INT64,
            difficulty_level INT64,
            difficulty_tier STRING,
            depth INT64,
            source_url STRING,
            concepts STRING[],
            sample_content STRING,
            PRIMARY KEY(topic_id)
        )
        """
    )
    conn.execute(
        """
        CREATE REL TABLE REQUIRES(
            FROM Topic TO Topic,
            strength DOUBLE,
            source STRING,
            evidence STRING
        )
        """
    )

    graph = json.loads((processed_for(chapter) / "graph.json").read_text(encoding="utf-8"))

    # Insert nodes
    for n in graph["nodes"]:
        conn.execute(
            """
            CREATE (t:Topic {
                topic_id: $topic_id,
                title: $title,
                description: $description,
                parent_section: $parent_section,
                parent_section_num: $parent_section_num,
                position_in_section: $position_in_section,
                difficulty_level: $difficulty_level,
                difficulty_tier: $difficulty_tier,
                depth: $depth,
                source_url: $source_url,
                concepts: $concepts,
                sample_content: $sample_content
            })
            """,
            {
                "topic_id": n["id"],
                "title": n.get("title", ""),
                "description": n.get("description", ""),
                "parent_section": n.get("parent_section", ""),
                "parent_section_num": str(n.get("parent_section_num", "")),
                "position_in_section": int(n.get("position_in_section", 0)),
                "difficulty_level": int(n.get("difficulty_level", 1)),
                "difficulty_tier": n.get("difficulty_tier", "easy"),
                "depth": int(n.get("depth", 0)),
                "source_url": n.get("source_url", ""),
                "concepts": _list_to_kuzu_str_array(n.get("concepts", [])),
                "sample_content": n.get("sample_content", ""),
            },
        )

    # Insert edges. The node-link format uses "edges" (we saved with
    # edges="edges"); fall back to "links" for older formats.
    edges = graph.get("edges") or graph.get("links") or []
    for e in edges:
        conn.execute(
            """
            MATCH (a:Topic), (b:Topic)
            WHERE a.topic_id = $src AND b.topic_id = $dst
            CREATE (a)-[:REQUIRES {
                strength: $strength,
                source: $source,
                evidence: $evidence
            }]->(b)
            """,
            {
                "src": e["source"],
                "dst": e["target"],
                "strength": float(e.get("strength", 1.0)),
                "source": str(e.get("source_type") or e.get("source") or ""),
                "evidence": e.get("evidence", ""),
            },
        )

    # Sanity-check queries
    n_nodes = conn.execute(
        "MATCH (t:Topic) RETURN count(t) AS n"
    ).get_next()[0]
    n_edges = conn.execute(
        "MATCH ()-[r:REQUIRES]->() RETURN count(r) AS n"
    ).get_next()[0]
    print(f"Kùzu DB: {n_nodes} topics, {n_edges} REQUIRES edges at {db_path}")

    # Demo query: frontier topics with shallow depth
    print("\nSample query — 5 topics with fewest prerequisites:")
    rs = conn.execute(
        """
        MATCH (t:Topic)
        OPTIONAL MATCH (p:Topic)-[:REQUIRES]->(t)
        WITH t, count(p) AS n_prereqs
        RETURN t.topic_id, t.title, t.difficulty_tier, n_prereqs
        ORDER BY n_prereqs ASC, t.parent_section_num ASC
        LIMIT 5
        """
    )
    while rs.has_next():
        row = rs.get_next()
        print(f"  {row[0]:18s} | {row[2]:6s} | prereqs={row[3]}  | {row[1]}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", type=int, default=1)
    args = ap.parse_args()
    run(args.chapter)
