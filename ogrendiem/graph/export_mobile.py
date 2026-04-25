"""Export processed graph data into the shape the React Native app consumes.

Reads
-----
data/processed/{scope}/topics.json
data/processed/{scope}/graph.json

Writes (into ../ogrendiem-app/assets/data/)
-------------------------------------------
topics.json     topics with emoji + garden_slot + cave_slot baked in
graph.json      node-link with slimmer payload
clusters.json   greedy-modularity clusters + short titles + colors
                ^^^ NOTE: these clusters are *visualization-only*. They are
                computed here, on the prereq DAG of the 55 in-scope topics,
                purely to give the Cave view its chambers. They have NO
                effect on the BKT engine, on prereq propagation, or on
                "next recommended topic" selection — those all run on the
                raw prereq edges in graph.json. If you delete clusters.json
                and stub it with one big cluster, the engine behavior is
                identical; only the Cave view changes shape. See the
                comment block above the `communities(...)` call in `run()`
                for more detail on why this re-clustering happens.
questions.json  (passes through existing bundled questions if present, else writes empty)

Run:
    python -m graph.export_mobile --scope g1-3-8-9
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from networkx.readwrite import json_graph

try:
    from . import parallelism
except ImportError:
    import parallelism

ROOT = Path(__file__).resolve().parent.parent                 # .../ogrendiem
REPO_ROOT = ROOT.parent                                       # .../toplumsal-katki
APP_ASSETS = REPO_ROOT / "ogrendiem-app" / "assets" / "data"

# ---------- emoji pools (curated, stable) ----------

GARDEN_POOL = [
    "🌸", "🌺", "🌻", "🌷", "🌹", "💐", "🌼", "🏵️",
    "🍎", "🍏", "🍐", "🍊", "🍋", "🍌", "🍉", "🍇",
    "🍓", "🫐", "🍒", "🍑", "🥭", "🍍", "🥥", "🥝",
    "🌰", "🌱", "🌿", "☘️", "🍀", "🍃", "🍂", "🍁",
    "🪴", "🌲", "🌳", "🌴", "🎋", "🎍", "🪷", "🌾",
]

CAVE_POOL = [
    "🐺", "🦊", "🐻", "🐼", "🐨", "🦁", "🐯", "🦝",
    "🐿️", "🦔", "🦇", "🦉", "🐢", "🦎", "🐍", "🦂",
    "🕷️", "🦋", "🐛", "🐌", "🪲", "🦗", "🐜", "🦙",
    "🦌", "🐗", "🐇", "🦫", "🦨", "🦡", "🐾", "💎",
    "🔮", "🪨", "💠", "🔷", "🔶", "✨", "🌟", "⭐",
]

# Perceptually distinct cluster colors
CLUSTER_PALETTE = [
    "#e74c3c", "#f39c12", "#f1c40f", "#2ecc71", "#1abc9c",
    "#9b59b6", "#e84393", "#00cec9", "#d35400", "#8e44ad",
]


def _hash_int(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)


def _pick_from(pool: list[str], seed: str) -> str:
    return pool[_hash_int(seed) % len(pool)]


# ---------- cluster titles (same heuristic as visualize_3d_clusters) ----------

def _cluster_title(G, members: set[str], max_words: int = 8) -> str:
    sections = [
        G.nodes[n].get("parent_section", "").strip()
        for n in members
        if G.nodes[n].get("parent_section")
    ]
    if not sections:
        titles = [G.nodes[n].get("title", "") for n in members]
        sections = [t for t in titles if t]
        if not sections:
            return "Topics"

    counts = Counter(sections)
    total = sum(counts.values())
    top = counts.most_common(2)
    if len(top) == 1 or top[0][1] / total >= 0.6:
        title = top[0][0]
    else:
        title = f"{top[0][0]} / {top[1][0]}"

    words = title.split()
    if len(words) > max_words:
        title = " ".join(words[:max_words]) + "…"
    return title


# ---------- garden layout (tree-in-nature, per chapter) ----------

def _garden_slots(G: nx.DiGraph, topics: list[dict]) -> dict[str, dict]:
    """For each topic, assign {branch, u}:
        branch = index of the section within its chapter (0..n-1)
        u      = position along the branch in [0,1], seeded by topic_id
    """
    # group topics by (chapter, section_num), in textbook order
    by_chapter: dict[str, list[str]] = defaultdict(list)
    section_order: dict[str, list[str]] = defaultdict(list)
    for t in topics:
        ch = str(t["parent_chapter_num"])
        sec = str(t["parent_section_num"])
        by_chapter[ch].append(t["topic_id"])
        if sec not in section_order[ch]:
            section_order[ch].append(sec)

    slot: dict[str, dict] = {}
    for t in topics:
        tid = t["topic_id"]
        ch = str(t["parent_chapter_num"])
        sec = str(t["parent_section_num"])
        branch = section_order[ch].index(sec)
        # u: position along the branch, seeded. Add small deterministic offset by
        # position_in_section so same-section topics don't overlap.
        rng = np.random.default_rng(_hash_int(tid) % (2**32))
        jitter = float(rng.uniform(-0.08, 0.08))
        pos_in_sec = int(t.get("position_in_section", 0))
        # Spread positions across 0.25..0.95 along the branch
        u = min(0.95, max(0.25, 0.35 + 0.12 * pos_in_sec + jitter))
        slot[tid] = {"branch": branch, "u": round(u, 4)}
    return slot


# ---------- cave layout (force-directed per cluster, normalized) ----------

def _cave_slots(G: nx.DiGraph, comms: list[set[str]]) -> dict[str, dict]:
    slot: dict[str, dict] = {}
    UG = G.to_undirected()
    for ci, members in enumerate(comms):
        sub = UG.subgraph(members)
        if len(members) == 1:
            (only,) = members
            slot[only] = {"cluster": ci, "x": 0.5, "y": 0.5}
            continue
        pos = nx.spring_layout(sub, seed=7, k=1.4, iterations=200)
        xs = np.array([pos[n][0] for n in members])
        ys = np.array([pos[n][1] for n in members])
        # Normalize to [0.08, 0.92] padding so nodes don't kiss the border
        def _norm(arr):
            lo, hi = arr.min(), arr.max()
            if hi - lo < 1e-9:
                return np.full_like(arr, 0.5)
            return 0.08 + 0.84 * (arr - lo) / (hi - lo)
        xs = _norm(xs)
        ys = _norm(ys)
        for n, x, y in zip(members, xs, ys):
            slot[n] = {"cluster": ci, "x": round(float(x), 4), "y": round(float(y), 4)}
    return slot


# ---------- main ----------

def run(scope: str) -> None:
    src = ROOT / "data" / "processed" / scope
    topics_src = json.loads((src / "topics.json").read_text(encoding="utf-8"))
    graph_src = json.loads((src / "graph.json").read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(graph_src, edges="edges")

    # --- clusters (loose communities, largest first) ---
    #
    # IMPORTANT: this is the SECOND application of greedy modularity in the
    # pipeline, and it is purely cosmetic.
    #
    # First application (elsewhere): greedy modularity is run on the
    # *chapter* graph to decide which textbook chapters bundle together
    # well — that is what produced the scope groups like `g1-3-8-9` that
    # the user picks from. By the time we get into this function, the
    # 55 topics in `G` are already the result of that choice.
    #
    # Second application (here): we run greedy modularity AGAIN, this time
    # on the prereq DAG of those 55 in-scope topics, to split them into
    # sub-communities. Each community becomes one chamber in the Cave
    # view in the React Native app — that is the only thing it is used for.
    #
    # These sub-clusters do NOT influence:
    #   - the BKT mastery posterior
    #   - noisy-AND prereq propagation
    #   - which topic is "next recommended" (frontier selection in
    #     ogrendiem-app/src/engine/local.ts uses raw prereq edges only)
    #   - the Garden tree view (which groups by chapter, not by cluster)
    #
    # If you replace `comms` below with `[set(G.nodes())]` (one big cluster
    # containing every topic), the engine and Garden behave identically;
    # only the Cave collapses to a single chamber.
    UG = parallelism.loose_subgraph(G)
    comms = sorted(parallelism.communities(UG), key=len, reverse=True)
    comms = [set(c) for c in comms]

    cluster_titles = [_cluster_title(G, m) for m in comms]
    cluster_of = {n: i for i, m in enumerate(comms) for n in m}

    # --- layout slots ---
    garden = _garden_slots(G, topics_src["topics"])
    cave = _cave_slots(G, comms)

    # --- emoji assignment ---
    garden_emoji = {t["topic_id"]: _pick_from(GARDEN_POOL, "garden:" + t["topic_id"])
                    for t in topics_src["topics"]}
    cave_emoji = {t["topic_id"]: _pick_from(CAVE_POOL, "cave:" + t["topic_id"])
                  for t in topics_src["topics"]}

    # --- topics.json (slim, with slots baked in) ---
    out_topics = []
    for t in topics_src["topics"]:
        tid = t["topic_id"]
        out_topics.append({
            "topic_id": tid,
            "title": t["title"],
            "parent_chapter_num": str(t["parent_chapter_num"]),
            "parent_section_num": str(t["parent_section_num"]),
            "parent_section": t["parent_section"],
            "position_in_section": int(t.get("position_in_section", 0)),
            "difficulty_level": int(t["difficulty_level"]),
            "difficulty_tier": t["difficulty_tier"],
            "depth": int(G.nodes[tid].get("depth", 0)),
            "description": t.get("description", "")[:500],
            "garden_emoji": garden_emoji[tid],
            "cave_emoji": cave_emoji[tid],
            "garden_slot": garden[tid],
            "cave_slot": cave[tid],
            "cluster_id": cluster_of.get(tid, -1),
        })

    topics_out = {
        "meta": {
            "scope": scope,
            "chapters": topics_src["meta"].get("chapters", []),
            "n_topics": len(out_topics),
            "n_edges": G.number_of_edges(),
        },
        "topics": out_topics,
    }

    # --- graph.json (slim) ---
    edges_out = [
        {"from": u, "to": v, "source": d.get("source", ""), "strength": d.get("strength", 1)}
        for u, v, d in G.edges(data=True)
    ]
    graph_out = {"nodes": [t["topic_id"] for t in out_topics], "edges": edges_out}

    # --- clusters.json ---
    clusters_out = {
        "clusters": [
            {
                "cluster_id": i,
                "title": cluster_titles[i],
                "color": CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)],
                "topic_ids": sorted(list(m)),
            }
            for i, m in enumerate(comms)
        ]
    }

    # --- write ---
    APP_ASSETS.mkdir(parents=True, exist_ok=True)
    (APP_ASSETS / "topics.json").write_text(
        json.dumps(topics_out, indent=2, ensure_ascii=False), encoding="utf-8")
    (APP_ASSETS / "graph.json").write_text(
        json.dumps(graph_out, indent=2, ensure_ascii=False), encoding="utf-8")
    (APP_ASSETS / "clusters.json").write_text(
        json.dumps(clusters_out, indent=2, ensure_ascii=False), encoding="utf-8")

    # questions.json is hand-curated elsewhere; don't overwrite if present
    q_path = APP_ASSETS / "questions.json"
    if not q_path.exists():
        q_path.write_text("[]", encoding="utf-8")

    print(f"Wrote {APP_ASSETS / 'topics.json'}")
    print(f"Wrote {APP_ASSETS / 'graph.json'}")
    print(f"Wrote {APP_ASSETS / 'clusters.json'}")
    print(f"Topics: {len(out_topics)}  Edges: {len(edges_out)}  Clusters: {len(comms)}")
    for i, title in enumerate(cluster_titles):
        print(f"  cluster {i}: {len(comms[i]):>2} topics — {title}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", type=str, default="g1-3-8-9")
    args = ap.parse_args()
    run(args.scope)
