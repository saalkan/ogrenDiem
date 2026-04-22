"""Find parallel-learnable substructure inside a scope's DAG.

"Strict" parallelism — pairs of topics that share no ancestor/descendant
relation — is narrow here (our graphs are near-chains). So we also look
for *loose* clusters: drop the weakest edge types and run community
detection on the undirected projection. That tends to surface coherent
thematic bundles (e.g. trig-identity topics, conics topics) that can be
learned largely in parallel once a shared prefix is mastered.

Usage:
    python -m graph.parallelism --scope g1-5-6-7
    python -m graph.parallelism --group 1-3-8-9
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ROOT = ROOT / "data" / "processed"

# Edge sources to drop when probing for *loose* parallelism. Structural
# edges artificially chain every chapter-end to the next chapter-start.
_LOOSE_DROP = {"structural-chap"}


def _load(scope: str) -> nx.DiGraph:
    path = PROCESSED_ROOT / scope / "graph.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return json_graph.node_link_graph(data, edges="edges")


def _title(G: nx.DiGraph, n: str) -> str:
    return G.nodes[n].get("title", n)


# ----------------------------------------------------------------------------
# Strict: antichain width per depth layer
# ----------------------------------------------------------------------------

def antichain_widths(G: nx.DiGraph) -> dict[int, list[str]]:
    """Group nodes by stored `depth` attribute. Nodes at the same depth
    are always an antichain if the DAG's depth = longest-path-from-root."""
    by_depth: dict[int, list[str]] = defaultdict(list)
    for n in G.nodes:
        by_depth[int(G.nodes[n].get("depth", 0))].append(n)
    return dict(sorted(by_depth.items()))


# ----------------------------------------------------------------------------
# Loose: components + communities after dropping structural-chap edges
# ----------------------------------------------------------------------------

def loose_subgraph(G: nx.DiGraph) -> nx.Graph:
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, d in G.edges(data=True):
        if d.get("source") in _LOOSE_DROP:
            continue
        H.add_edge(u, v, **d)
    return H.to_undirected()


def communities(UG: nx.Graph) -> list[set[str]]:
    """Greedy modularity communities — ships with networkx, no extra deps."""
    try:
        from networkx.algorithms.community import greedy_modularity_communities
    except ImportError:  # very old networkx
        return [set(c) for c in nx.connected_components(UG)]
    return [set(c) for c in greedy_modularity_communities(UG)]


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------

def _chapter_of(n: str, G: nx.DiGraph) -> str:
    v = G.nodes[n].get("parent_chapter_num")
    if v:
        return str(v)
    # Fallback: topic_id looks like 'ch{N}_s{sec}_t{i}'
    if n.startswith("ch") and "_" in n:
        return n[2:].split("_", 1)[0]
    return "?"


def _summarise_cluster(G: nx.DiGraph, members: set[str]) -> dict:
    chapters = sorted({_chapter_of(n, G) for n in members})
    sections = sorted({
        f"{_chapter_of(n, G)}.{G.nodes[n].get('parent_section_num','?')}"
        for n in members
    })
    depths = [int(G.nodes[n].get("depth", 0)) for n in members]
    return {
        "size": len(members),
        "chapters": chapters,
        "sections": sections,
        "depth_range": (min(depths), max(depths)) if depths else (0, 0),
        "members": sorted(members, key=lambda n: int(G.nodes[n].get("depth", 0))),
    }


def run(scope: str) -> None:
    G = _load(scope)
    n = G.number_of_nodes()
    print(f"\n=== {scope}  ({n} nodes, {G.number_of_edges()} edges) ===\n")

    # --- Strict antichains
    widths = antichain_widths(G)
    max_w = max(len(v) for v in widths.values())
    print(f"Strict antichain widths by depth (max layer width = {max_w}):")
    for d, nodes in widths.items():
        if len(nodes) >= 2:
            titles = ", ".join(_title(G, x) for x in nodes)
            print(f"  depth {d:>2}: {len(nodes):>2} nodes  — {titles}")
    if max_w == 1:
        print("  (every layer has a single node — strictly a chain)")
    print()

    # --- Loose: drop structural-chap, find components + communities
    UG = loose_subgraph(G)
    wccs = sorted(nx.connected_components(UG), key=len, reverse=True)
    print(f"Loose components (dropping {sorted(_LOOSE_DROP)}): {len(wccs)}")
    for i, comp in enumerate(wccs, 1):
        s = _summarise_cluster(G, set(comp))
        print(f"  component {i}: size={s['size']}  chapters={s['chapters']}")

    print()
    comms = sorted(communities(UG), key=len, reverse=True)
    print(f"Loose communities (greedy modularity): {len(comms)}")
    for i, c in enumerate(comms, 1):
        s = _summarise_cluster(G, c)
        print(
            f"  cluster {i}: size={s['size']:>2}  "
            f"ch={s['chapters']}  depth {s['depth_range'][0]}–{s['depth_range'][1]}"
        )
        for tid in s["members"][:8]:
            print(f"      {tid}  {_title(G, tid)}")
        if len(s["members"]) > 8:
            print(f"      … +{len(s['members']) - 8} more")


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
