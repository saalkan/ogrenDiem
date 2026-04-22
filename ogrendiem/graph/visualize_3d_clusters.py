"""Static 3D DAG view with pre-colored loose-community clusters.

Each greedy-modularity community gets its own color and edge thickness.
Cross-cluster edges stay dim grey so the thematic groupings pop. No
on-click interactivity — this file is meant to render instantly.

Writes:
    data/processed/{scope}/graph_3d_clusters.html
"""
from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
from networkx.readwrite import json_graph

try:
    from .visualize_3d import _layered_3d_positions, _hover_text, PROCESSED_ROOT
    from . import parallelism
except ImportError:
    from visualize_3d import _layered_3d_positions, _hover_text, PROCESSED_ROOT
    import parallelism

ROOT = Path(__file__).resolve().parent.parent

# Perceptually distinct palette for clusters (avoid blue — it's the
# default "everything else" colour). Cycles for large community counts.
CLUSTER_PALETTE = [
    "#e74c3c",  # red
    "#f39c12",  # orange
    "#f1c40f",  # yellow
    "#2ecc71",  # green
    "#1abc9c",  # teal
    "#9b59b6",  # purple
    "#e84393",  # pink
    "#00cec9",  # cyan
    "#d35400",  # burnt orange
    "#8e44ad",  # deep purple
]

# Edge thickness per cluster rank (largest first). Cycles beyond 6 clusters.
CLUSTER_WIDTHS = [8, 7, 6, 5, 4, 3]

CROSS_EDGE_COLOR = "rgba(140,140,140,0.35)"
CROSS_EDGE_WIDTH = 1


def _cluster_of(G, members_by_cluster: list[set[str]]) -> dict[str, int]:
    mapping = {}
    for i, members in enumerate(members_by_cluster):
        for n in members:
            mapping[n] = i
    return mapping


def _cluster_title(G, members: set[str], max_words: int = 7) -> str:
    """Short descriptive label derived from the cluster's dominant section titles.

    Heuristic: rank the `parent_section` strings by frequency; if one covers
    ≥ 60% of the cluster, use it alone; otherwise join the top two with ' / '.
    Clamp to `max_words` words so legend rows stay single-line.
    """
    from collections import Counter

    sections = [
        G.nodes[n].get("parent_section", "").strip()
        for n in members
        if G.nodes[n].get("parent_section")
    ]
    if not sections:
        # Fallback to the most common topic title (rare)
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


def build_figure(G, title_label: str) -> go.Figure:
    pos = _layered_3d_positions(G)

    # Loose communities (drops structural-chap glue edges before community
    # detection) — same as graph.parallelism.
    UG = parallelism.loose_subgraph(G)
    comms = sorted(parallelism.communities(UG), key=len, reverse=True)
    comms = [set(c) for c in comms]
    cluster_of = _cluster_of(G, comms)

    traces: list = []

    # --- Cross-cluster edges, dim grey ---
    cx, cy, cz = [], [], []
    for u, v in G.edges():
        if cluster_of.get(u) == cluster_of.get(v):
            continue
        x0, y0, z0 = pos[u]
        x1, y1, z1 = pos[v]
        cx += [x0, x1, None]
        cy += [y0, y1, None]
        cz += [z0, z1, None]
    traces.append(go.Scatter3d(
        x=cx, y=cy, z=cz,
        mode="lines",
        line=dict(color=CROSS_EDGE_COLOR, width=CROSS_EDGE_WIDTH),
        hoverinfo="none",
        name="cross-cluster",
        showlegend=False,
    ))

    # --- One edge trace per cluster, coloured + thickened ---
    for i, members in enumerate(comms):
        color = CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)]
        width = CLUSTER_WIDTHS[i % len(CLUSTER_WIDTHS)]
        ex, ey, ez = [], [], []
        for u, v in G.edges():
            if u not in members or v not in members:
                continue
            x0, y0, z0 = pos[u]
            x1, y1, z1 = pos[v]
            ex += [x0, x1, None]
            ey += [y0, y1, None]
            ez += [z0, z1, None]
        traces.append(go.Scatter3d(
            x=ex, y=ey, z=ez,
            mode="lines",
            line=dict(color=color, width=width),
            hoverinfo="none",
            showlegend=False,
            name=f"cluster-{i+1}-edges",
        ))

    # --- One node trace per cluster (for legend + colour) ---
    for i, members in enumerate(comms):
        color = CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)]
        nodes = sorted(members)
        if not nodes:
            continue
        xs = [pos[n][0] for n in nodes]
        ys = [pos[n][1] for n in nodes]
        zs = [pos[n][2] for n in nodes]
        labels = [G.nodes[n].get("title", n) for n in nodes]
        hovers = [_hover_text(G, n) for n in nodes]
        chapters = sorted({
            (G.nodes[n].get("parent_chapter_num")
             or (n[2:].split("_", 1)[0] if n.startswith("ch") and "_" in n else "?"))
            for n in nodes
        })
        cluster_title = _cluster_title(G, set(nodes))
        legend_name = (
            f"Cluster {i+1}: {cluster_title} · "
            f"{len(nodes)} topics · ch {','.join(chapters)}"
        )
        traces.append(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="markers+text",
            text=labels,
            textposition="top center",
            textfont=dict(size=10, color="#74b9ff"),
            marker=dict(
                size=13,
                color=color,
                line=dict(color="#111", width=1),
                opacity=0.96,
            ),
            hovertext=hovers,
            hoverinfo="text",
            name=legend_name,
        ))

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=dict(
            text=f"Precalculus {title_label} — Clusters (3D)",
            font=dict(color="#74b9ff"),
        ),
        paper_bgcolor="#111",
        scene=dict(
            bgcolor="#111",
            xaxis=dict(title="depth", color="#888", gridcolor="#333", zerolinecolor="#333"),
            yaxis=dict(title="", color="#888", gridcolor="#333",
                       zerolinecolor="#333", showticklabels=False),
            zaxis=dict(title="", color="#888", gridcolor="#333",
                       zerolinecolor="#333", showticklabels=False),
            camera=dict(eye=dict(x=1.8, y=1.6, z=1.2)),
        ),
        legend=dict(
            font=dict(color="#74b9ff", size=11),
            bgcolor="rgba(0,0,0,0.35)",
            bordercolor="#333",
            borderwidth=1,
        ),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def run(scope: str) -> None:
    d = PROCESSED_ROOT / scope
    graph_json = d / "graph.json"
    out = d / "graph_3d_clusters.html"
    if not graph_json.exists():
        raise SystemExit(
            f"{graph_json} missing — run `python -m graph.build` for scope '{scope}' first."
        )
    data = json.loads(graph_json.read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(data, edges="edges")

    topics_json = d / "topics.json"
    title_label = f"({scope})"
    if topics_json.exists():
        meta = json.loads(topics_json.read_text(encoding="utf-8")).get("meta", {})
        chapters = meta.get("chapters") or ([meta["chapter"]] if meta.get("chapter") else [])
        if len(chapters) == 1:
            title_label = f"Ch. {chapters[0]}"
        elif chapters:
            title_label = "Chs. " + ", ".join(str(c) for c in chapters)

    fig = build_figure(G, title_label)
    fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
    print(f"Wrote {out}")


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
    g.add_argument("--chapter", type=int)
    g.add_argument("--group", type=str)
    g.add_argument("--scope", type=str)
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
