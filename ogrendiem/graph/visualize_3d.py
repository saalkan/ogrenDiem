"""Interactive 3D view of the prerequisite DAG using Plotly.

Run:
    python -m graph.visualize_3d

Writes:
    data/processed/graph_3d.html

Open the HTML in any browser — left-drag to orbit, scroll to zoom,
right-drag to pan, hover over a node for its metadata.

Layout
------
The X axis is depth in the DAG (topological distance from roots).
Y and Z are obtained from a 3D spring layout applied layer-by-layer,
so nodes at the same depth don't overlap but the overall flow still
reads left → right.
"""
from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import numpy as np
import plotly.graph_objects as go
from networkx.readwrite import json_graph

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ROOT = ROOT / "data" / "processed"


def _paths(scope: str) -> tuple[Path, Path]:
    d = PROCESSED_ROOT / scope
    return d / "graph.json", d / "graph_3d.html"

TIER_COLORS = {"easy": "#6ab04c", "medium": "#f0932b", "hard": "#eb4d4b"}


def _layered_3d_positions(G: nx.DiGraph, seed: int = 7) -> dict[str, tuple[float, float, float]]:
    """X = depth (layer). Y, Z = 2D spring embedding of the *undirected*
    projection of the graph, rescaled per-layer so each layer sits inside
    its own disc."""
    depth = {n: int(G.nodes[n].get("depth", 0)) for n in G.nodes}
    max_depth = max(depth.values()) if depth else 0
    n_nodes = G.number_of_nodes()

    # Scale layer spacing and disc radius with graph size so dense (group)
    # graphs aren't cramped. Base values unchanged for small single-chapter
    # graphs (~10–20 nodes); roughly doubles by 50 nodes.
    size_scale = max(1.0, (n_nodes / 15) ** 0.5)
    layer_spacing = 2.5 * size_scale
    disc_radius = 1.5 * size_scale

    # Global YZ spring layout (undirected so edges pull neighbours together).
    UG = G.to_undirected()
    pos2d = nx.spring_layout(UG, dim=2, seed=seed, k=1.2, iterations=200)

    # Collect per-layer membership.
    layers: dict[int, list[str]] = {}
    for n, d in depth.items():
        layers.setdefault(d, []).append(n)

    pos3d: dict[str, tuple[float, float, float]] = {}
    for d, nodes in layers.items():
        ys = np.array([pos2d[n][0] for n in nodes])
        zs = np.array([pos2d[n][1] for n in nodes])
        if len(nodes) > 1:
            ys -= ys.mean()
            zs -= zs.mean()
            scale = max(float(np.ptp(ys)), float(np.ptp(zs)), 1e-6)
            ys = ys / scale * disc_radius
            zs = zs / scale * disc_radius
        x = d * layer_spacing
        for i, n in enumerate(nodes):
            pos3d[n] = (x, float(ys[i]), float(zs[i]))

    # If a node lacks depth (shouldn't happen after graph/build.py), put it at 0
    for n in G.nodes:
        if n not in pos3d:
            pos3d[n] = (0.0, float(np.random.randn()), float(np.random.randn()))

    return pos3d


def _hover_text(G: nx.DiGraph, n: str) -> str:
    d = G.nodes[n]
    parents = list(G.predecessors(n))
    children = list(G.successors(n))
    lines = [
        f"<b>{d.get('title', n)}</b>",
        f"<i>id:</i> {n}",
        f"<i>section:</i> {d.get('parent_section_num', '?')}"
        f" &nbsp;·&nbsp; <i>difficulty:</i> {d.get('difficulty_level', '?')}"
        f" ({d.get('difficulty_tier', '?')})"
        f" &nbsp;·&nbsp; <i>depth:</i> {d.get('depth', '?')}",
        "",
        f"{d.get('description', '')[:260].replace(chr(10), '<br>')}",
    ]
    if parents:
        lines.append("")
        lines.append("<b>Prerequisites:</b>")
        for p in parents:
            lines.append(f"  · {G.nodes[p].get('title', p)}")
    if children:
        lines.append("")
        lines.append("<b>Unlocks:</b>")
        for c in children:
            lines.append(f"  · {G.nodes[c].get('title', c)}")
    return "<br>".join(lines)


def build_figure(G: nx.DiGraph, title_label: str = "Ch. 1") -> go.Figure:
    pos = _layered_3d_positions(G)

    # --- Edges as line segments. We flatten into one scatter trace with
    # None separators so Plotly draws disconnected segments.
    ex, ey, ez = [], [], []
    # For arrow "heads", we also draw a cone at each edge's target.
    cone_x, cone_y, cone_z, cone_u, cone_v, cone_w = [], [], [], [], [], []
    for u, v in G.edges():
        x0, y0, z0 = pos[u]
        x1, y1, z1 = pos[v]
        ex += [x0, x1, None]
        ey += [y0, y1, None]
        ez += [z0, z1, None]
        # Arrow cone vector (slightly shortened, pointing toward target)
        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
        cone_x.append(x1)
        cone_y.append(y1)
        cone_z.append(z1)
        cone_u.append(dx)
        cone_v.append(dy)
        cone_w.append(dz)

    edge_trace = go.Scatter3d(
        x=ex, y=ey, z=ez,
        mode="lines",
        line=dict(color="rgba(78, 161, 255, 0.70)", width=2),
        hoverinfo="none",
        showlegend=False,
    )

    arrow_trace = go.Cone(
        x=cone_x, y=cone_y, z=cone_z,
        u=cone_u, v=cone_v, w=cone_w,
        sizemode="absolute",
        sizeref=0.25,
        anchor="tip",
        showscale=False,
        colorscale=[[0, "rgba(78, 161, 255, 0.80)"], [1, "rgba(78, 161, 255, 0.80)"]],
        hoverinfo="none",
        showlegend=False,
    )

    # --- Node traces, one per tier for legend + color control
    node_traces = []
    for tier, color in TIER_COLORS.items():
        members = [n for n in G.nodes if G.nodes[n].get("difficulty_tier") == tier]
        if not members:
            continue
        xs = [pos[n][0] for n in members]
        ys = [pos[n][1] for n in members]
        zs = [pos[n][2] for n in members]
        labels = [G.nodes[n].get("title", n) for n in members]
        hovers = [_hover_text(G, n) for n in members]
        node_traces.append(
            go.Scatter3d(
                x=xs, y=ys, z=zs,
                mode="markers+text",
                text=labels,
                textposition="top center",
                textfont=dict(size=10, color="#74b9ff"),
                marker=dict(
                    size=12,
                    color=color,
                    line=dict(color="#111", width=1),
                    opacity=0.95,
                ),
                hovertext=hovers,
                hoverinfo="text",
                name=tier,
            )
        )

    fig = go.Figure(data=[edge_trace, arrow_trace, *node_traces])
    fig.update_layout(
        title=dict(
            text=f"Precalculus {title_label} — Prerequisite DAG (3D)",
            font=dict(color="#74b9ff"),
        ),
        paper_bgcolor="#111",
        scene=dict(
            bgcolor="#111",
            xaxis=dict(title="depth", color="#888", gridcolor="#333", zerolinecolor="#333"),
            yaxis=dict(title="", color="#888", gridcolor="#333", zerolinecolor="#333",
                       showticklabels=False),
            zaxis=dict(title="", color="#888", gridcolor="#333", zerolinecolor="#333",
                       showticklabels=False),
            camera=dict(eye=dict(x=1.8, y=1.6, z=1.2)),
        ),
        legend=dict(font=dict(color="#74b9ff"), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def run(scope: str = "ch1") -> None:
    graph_json, out = _paths(scope)
    if not graph_json.exists():
        raise SystemExit(
            f"{graph_json} missing — run "
            f"`python -m graph.build` for scope '{scope}' first."
        )
    data = json.loads(graph_json.read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(data, edges="edges")
    # Derive a human-readable title from the processed topics.json if present.
    topics_json = PROCESSED_ROOT / scope / "topics.json"
    title_label = f"({scope})"
    if topics_json.exists():
        meta = json.loads(topics_json.read_text(encoding="utf-8")).get("meta", {})
        chapters = meta.get("chapters") or ([meta["chapter"]] if meta.get("chapter") else [])
        if len(chapters) == 1:
            title_label = f"Ch. {chapters[0]}"
        elif chapters:
            title_label = "Chs. " + ", ".join(str(c) for c in chapters)
    fig = build_figure(G, title_label=title_label)
    fig.write_html(str(out), include_plotlyjs="cdn", full_html=True)
    print(f"Wrote {out}")
    print("Open it in your browser — orbit by dragging, scroll to zoom, hover for details.")


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
