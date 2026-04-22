"""Build the prerequisite DAG in NetworkX, validate it, compute depth,
serialise to JSON, and render a visualisation.

Inputs
------
data/processed/topics.json  (from nlp/extract.py)

Outputs
-------
data/processed/graph.json            node-link JSON (re-loadable via NetworkX)
data/processed/graph.png             matplotlib DAG visualisation
data/processed/graph_interactive.html  pyvis interactive graph (optional)
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
from networkx.readwrite import json_graph

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ROOT = ROOT / "data" / "processed"


def processed_dir(scope: str) -> Path:
    d = PROCESSED_ROOT / scope
    d.mkdir(parents=True, exist_ok=True)
    return d


# ----------------------------------------------------------------------------
# Build
# ----------------------------------------------------------------------------

def _truncate(text: str, limit: int) -> str:
    """Truncate to `limit` characters, appending '…' when clipped."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _wrap(text: str, width: int = 50) -> str:
    """Insert newlines at ~`width`-char boundaries, breaking on whitespace
    when possible so words stay intact."""
    import textwrap
    text = (text or "").strip()
    if not text:
        return text
    return "\n".join(
        textwrap.wrap(
            text,
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
    ) or text


def _edge_weight(source: str) -> float:
    """Higher = stronger claim. Used to decide which edge to drop when
    breaking cycles."""
    return {
        "term-definition": 4,
        "explicit-ref": 3,
        "structural-sec": 2,
        "structural-chap": 1,
    }.get(source, 0)


def build_graph(topics_path: Path) -> tuple[nx.DiGraph, dict]:
    data = json.loads(topics_path.read_text(encoding="utf-8"))
    G = nx.DiGraph()

    for t in data["topics"]:
        G.add_node(
            t["topic_id"],
            title=t["title"],
            description=_wrap(t["description"], 50),
            parent_section=t["parent_section"],
            parent_section_num=t["parent_section_num"],
            position_in_section=t["position_in_section"],
            difficulty_level=t["difficulty_level"],
            difficulty_tier=t["difficulty_tier"],
            concepts=t["concepts"],
            defined_terms=t.get("defined_terms", []),
            sample_content=t["sample_content"],
            source_url=t["source_url"],
        )

    for e in data["edges"]:
        G.add_edge(
            e["from"], e["to"],
            strength=_edge_weight(e["source"]),
            source=e["source"],
            evidence=e.get("evidence", ""),
        )

    return G, data


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def break_cycles(G: nx.DiGraph) -> list[tuple[str, str]]:
    """If cycles exist, drop the weakest edge in each cycle until the graph
    is acyclic. Return the list of removed edges."""
    removed: list[tuple[str, str]] = []
    while not nx.is_directed_acyclic_graph(G):
        cycle = nx.find_cycle(G, orientation="original")
        # cycle items are (u, v, 'forward') tuples here
        weakest = min(cycle, key=lambda uv: G[uv[0]][uv[1]]["strength"])
        u, v = weakest[0], weakest[1]
        G.remove_edge(u, v)
        removed.append((u, v))
    return removed


def find_orphans(G: nx.DiGraph) -> list[str]:
    """Non-root nodes should have ≥ 1 prerequisite.

    For the slice, "root" means no incoming edges. The chapter's first
    topic(s) are legitimately root; we just report the rest."""
    # A topic is only suspicious if it has no incoming edge AND it's not
    # plausibly a chapter entry point (section 1 position 0).
    suspects: list[str] = []
    for n, deg in G.in_degree():
        if deg != 0:
            continue
        sec = G.nodes[n].get("parent_section_num", "0")
        pos = G.nodes[n].get("position_in_section", 0)
        if str(sec) == "1" and pos == 0:
            continue
        suspects.append(n)
    return suspects


def find_difficulty_inversions(G: nx.DiGraph) -> list[tuple[str, str, int, int]]:
    """An edge from a high-difficulty topic to a low-difficulty one suggests
    a broken prerequisite. Return (u, v, du, dv) for every edge where
    du - dv >= 2 (a generous threshold for the slice)."""
    bad: list[tuple[str, str, int, int]] = []
    for u, v in G.edges():
        du = G.nodes[u]["difficulty_level"]
        dv = G.nodes[v]["difficulty_level"]
        if du - dv >= 2:
            bad.append((u, v, du, dv))
    return bad


def compute_depth(G: nx.DiGraph) -> dict[str, int]:
    """Longest path from any root to each node. Requires the graph be a DAG."""
    depth: dict[str, int] = {}
    for n in nx.topological_sort(G):
        preds = list(G.predecessors(n))
        depth[n] = 0 if not preds else 1 + max(depth[p] for p in preds)
    return depth


# ----------------------------------------------------------------------------
# Visualisation
# ----------------------------------------------------------------------------

_TIER_COLORS = {"easy": "#6ab04c", "medium": "#f0932b", "hard": "#eb4d4b"}


def _layered_pos(G: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Position nodes in horizontal layers by depth. Within a layer, order
    by section number then title for legibility."""
    depth = {n: G.nodes[n].get("depth", 0) for n in G.nodes}
    by_layer: dict[int, list[str]] = {}
    for n, d in depth.items():
        by_layer.setdefault(d, []).append(n)
    # Scale horizontal/vertical spacing with graph size so big (group)
    # graphs don't overlap labels.
    n_nodes = G.number_of_nodes()
    size_scale = max(1.0, (n_nodes / 15) ** 0.5)
    x_spacing = 2.5 * size_scale
    y_spacing = 1.2 * size_scale
    pos: dict[str, tuple[float, float]] = {}
    for d, nodes in by_layer.items():
        nodes_sorted = sorted(
            nodes,
            key=lambda n: (
                float(G.nodes[n].get("parent_section_num") or 0),
                G.nodes[n].get("position_in_section", 0),
            ),
        )
        n_here = len(nodes_sorted)
        for i, n in enumerate(nodes_sorted):
            x = d * x_spacing
            y = -(i - (n_here - 1) / 2) * y_spacing
            pos[n] = (x, y)
    return pos


def render_static(G: nx.DiGraph, out_path: Path, title_label: str = "Ch. 1") -> None:
    pos = _layered_pos(G)
    colors = [_TIER_COLORS[G.nodes[n]["difficulty_tier"]] for n in G.nodes]
    labels = {n: G.nodes[n]["title"] for n in G.nodes}

    plt.figure(figsize=(16, 10))
    nx.draw_networkx_edges(
        G, pos, arrows=True, arrowsize=12, edge_color="#4ea1ff", width=1.1, alpha=0.75
    )
    nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=1100, alpha=0.95)
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=7)
    plt.title(
        f"Precalculus {title_label} — Prerequisite DAG  "
        "(green easy, orange medium, red hard)"
    )
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def render_interactive(G: nx.DiGraph, out_path: Path) -> None:
    try:
        from pyvis.network import Network
    except ImportError:
        print("pyvis not installed, skipping interactive render")
        return
    net = Network(height="800px", width="100%", directed=True, bgcolor="#111", font_color="#74b9ff")
    net.toggle_physics(True)
    # Longer springs + weaker gravity so dense group graphs spread out.
    n_nodes = G.number_of_nodes()
    spring_length = int(150 * max(1.0, (n_nodes / 15) ** 0.5))
    net.barnes_hut(
        gravity=-20000,
        central_gravity=0.15,
        spring_length=spring_length,
        spring_strength=0.02,
        damping=0.25,
    )
    for n, data in G.nodes(data=True):
        color = _TIER_COLORS[data["difficulty_tier"]]
        title = (
            f"<b>{data['title']}</b><br>"
            f"§ {data['parent_section_num']} · difficulty {data['difficulty_level']} "
            f"({data['difficulty_tier']})<br>"
            f"<i>{data['description'].replace(chr(10), '<br>')}</i>"
        )
        net.add_node(n, label=data["title"], color=color, title=title)
    for u, v, d in G.edges(data=True):
        net.add_edge(
            u, v,
            title=f"{d['source']} ({d.get('evidence', '')})",
            value=d["strength"],
        )
    # pyvis .show() writes the html; .save_graph avoids trying to open a browser
    net.save_graph(str(out_path))


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------

def run(scope: str = "ch1") -> None:
    processed = processed_dir(scope)
    topics_path = processed / "topics.json"
    if not topics_path.exists():
        raise SystemExit(
            f"{topics_path} missing — run "
            f"`python -m nlp.extract` for scope '{scope}' first."
        )
    G, data = build_graph(topics_path)
    meta = data.get("meta", {})
    chapters = meta.get("chapters") or ([meta["chapter"]] if meta.get("chapter") else [])
    if len(chapters) <= 1:
        title_label = f"Ch. {chapters[0]}" if chapters else f"({scope})"
    else:
        title_label = "Chs. " + ", ".join(str(c) for c in chapters)

    n0, e0 = G.number_of_nodes(), G.number_of_edges()
    print(f"Loaded: {n0} nodes, {e0} edges")

    removed = break_cycles(G)
    if removed:
        print(f"Removed {len(removed)} edges to make the graph acyclic:")
        for u, v in removed:
            print(f"  - {u} → {v}")
    else:
        print("Graph is already a DAG.")

    orphans = find_orphans(G)
    if orphans:
        print(f"Unusual roots ({len(orphans)}):")
        for o in orphans:
            t = G.nodes[o]["title"]
            print(f"  - {o}  ({t})")

    inversions = find_difficulty_inversions(G)
    if inversions:
        print(f"Difficulty inversions ({len(inversions)}):")
        for u, v, du, dv in inversions:
            print(f"  - {u} (D={du}) → {v} (D={dv})")

    # Compute and attach depth
    depth = compute_depth(G)
    for n, d in depth.items():
        G.nodes[n]["depth"] = d

    # Serialise
    graph_json = json_graph.node_link_data(G, edges="edges")
    (processed / "graph.json").write_text(
        json.dumps(graph_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote {processed / 'graph.json'}")

    # Render
    png_path = processed / "graph.png"
    render_static(G, png_path, title_label=title_label)
    print(f"Wrote {png_path}")

    html_path = processed / "graph_interactive.html"
    render_interactive(G, html_path)
    print(f"Wrote {html_path}")

    # Summary
    print()
    print(f"Final: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"Max depth: {max(depth.values())}")
    print(
        "Roots (no prerequisites): "
        + ", ".join(n for n, d in G.in_degree() if d == 0)
    )


if __name__ == "__main__":
    import argparse
    try:
        from scraper.seed_urls import chapters_for, scope_label
    except ImportError:
        import sys
        sys.path.insert(0, str(ROOT / "scraper"))
        from seed_urls import chapters_for, scope_label

    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--chapter", type=int, help="single chapter number")
    g.add_argument("--group", type=str, help="group label like '1-2-3-4'")
    g.add_argument("--scope", type=str, help="raw scope label like 'ch1' or 'g1-2-3-4'")
    args = ap.parse_args()
    if args.scope:
        scope = args.scope
    elif args.group:
        scope = scope_label(chapters_for(args.group))
    elif args.chapter is not None:
        scope = f"ch{args.chapter}"
    else:
        scope = "ch1"
    run(scope)
