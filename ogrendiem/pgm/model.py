"""Assemble a pgmpy Bayesian network from the DAG and provide a friendly
inference surface for the tutoring loop.

Given `data/processed/graph.json` (produced by graph/build.py), this module
builds a DiscreteBayesianNetwork whose structure mirrors the DAG and whose
CPTs are instantiated from the templates in `pgm.cpts`.

Runtime usage
-------------
    tutor = TutorModel.from_graph()
    beliefs = tutor.marginals()
    tutor.observe("ch1_s1_t1", difficulty="medium", correct=True)
    beliefs = tutor.marginals()     # reflects the observation
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Iterable

from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination
from pgmpy.models import DiscreteBayesianNetwork

from .cpts import (
    PRIOR,
    P_CORRECT,
    STATES,
    child_row,
)

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ROOT = ROOT / "data" / "processed"


def graph_json_for(chapter: int) -> Path:
    return PROCESSED_ROOT / f"ch{chapter}" / "graph.json"


# ----------------------------------------------------------------------------
# Network assembly
# ----------------------------------------------------------------------------

def _root_cpd(topic_id: str, tier: str) -> TabularCPD:
    probs = PRIOR[tier]
    return TabularCPD(
        variable=topic_id,
        variable_card=3,
        values=[[p] for p in probs],
        state_names={topic_id: STATES},
    )


def _child_cpd(topic_id: str, tier: str, parents: list[str]) -> TabularCPD:
    """Build the full conditional table for a topic given its parents
    using the weakest-link aggregation.

    pgmpy expects a (variable_card, product-of-parent-cards) matrix in
    row-major order where the *last* evidence variable varies fastest.
    We enumerate parent state tuples with itertools.product; the order of
    that product matches pgmpy's expectation when the evidence list given
    to TabularCPD is in the same order we iterate."""
    parent_cards = [3] * len(parents)
    # Column order: parents[0] varies slowest, parents[-1] fastest.
    combos = list(itertools.product(STATES, repeat=len(parents)))
    # For each combination, compute child distribution
    cols: list[list[float]] = []
    for combo in combos:
        cols.append(child_row(tier, combo))
    # Transpose to pgmpy's expected (variable_card, n_combos) shape.
    values = [[col[i] for col in cols] for i in range(3)]
    return TabularCPD(
        variable=topic_id,
        variable_card=3,
        values=values,
        evidence=parents,
        evidence_card=parent_cards,
        state_names={topic_id: STATES, **{p: STATES for p in parents}},
    )


def build_network(graph_path: Path) -> tuple[DiscreteBayesianNetwork, dict]:
    data = json.loads(graph_path.read_text(encoding="utf-8"))

    bn = DiscreteBayesianNetwork()
    nodes_by_id = {n["id"]: {**n, "topic_id": n["id"]} for n in data["nodes"]}
    for tid in nodes_by_id:
        bn.add_node(tid)

    edges = data.get("edges") or data.get("links") or []
    for e in edges:
        bn.add_edge(e["source"], e["target"])

    # CPDs
    for tid, node in nodes_by_id.items():
        tier = node["difficulty_tier"]
        parents = list(bn.get_parents(tid))
        if not parents:
            cpd = _root_cpd(tid, tier)
        else:
            cpd = _child_cpd(tid, tier, parents)
        bn.add_cpds(cpd)

    assert bn.check_model(), "pgmpy reports an invalid model"
    return bn, nodes_by_id


# ----------------------------------------------------------------------------
# Tutor-facing wrapper
# ----------------------------------------------------------------------------

class TutorModel:
    """Thin façade over a DiscreteBayesianNetwork: holds accumulated virtual
    evidence from answered questions and exposes marginal queries."""

    # Temperature applied to each observation's likelihood vector before it
    # becomes a virtual-evidence factor. τ = 1 is the plain Bayesian update;
    # τ > 1 damps a single observation so one wrong answer can't flip argmax
    # by itself; τ → ∞ ignores evidence entirely. Exposed as an attribute so
    # it can be tuned (or, later, fit by cross-validated log-loss on held-out
    # answer sequences).
    DEFAULT_TEMPERATURE = 1.5

    def __init__(
        self,
        bn: DiscreteBayesianNetwork,
        nodes_by_id: dict,
        temperature: float | None = None,
    ):
        self.bn = bn
        self.nodes = nodes_by_id
        self.chapter: int | None = None  # set by from_graph() when known
        self._infer = VariableElimination(bn)
        self.temperature = (
            self.DEFAULT_TEMPERATURE if temperature is None else float(temperature)
        )
        # accumulated virtual evidence: list of TabularCPD (one per
        # answered question) representing the likelihood vector
        self._virtual_evidence: list[TabularCPD] = []
        self._history: list[dict] = []

    # --- construction helpers -----------------------------------------------

    @classmethod
    def from_graph(
        cls,
        chapter: int = 1,
        graph_path: Path | None = None,
        temperature: float | None = None,
    ) -> "TutorModel":
        path = graph_path if graph_path is not None else graph_json_for(chapter)
        if not path.exists():
            raise SystemExit(
                f"{path} missing — run the graph build for chapter {chapter} first:\n"
                f"  python -m scraper.scrape  --chapter {chapter}\n"
                f"  python -m nlp.extract     --chapter {chapter}\n"
                f"  python -m graph.build     --chapter {chapter}\n"
            )
        bn, nodes = build_network(path)
        tm = cls(bn, nodes, temperature=temperature)
        tm.chapter = chapter
        return tm

    # --- introspection ------------------------------------------------------

    @property
    def topic_ids(self) -> list[str]:
        return list(self.nodes.keys())

    def title(self, topic_id: str) -> str:
        return self.nodes[topic_id]["title"]

    def tier(self, topic_id: str) -> str:
        return self.nodes[topic_id]["difficulty_tier"]

    # --- evidence handling --------------------------------------------------

    def observe(self, topic_id: str, difficulty: str, correct: bool) -> None:
        """Record the outcome of one question.

        difficulty ∈ {easy, medium, hard}; correct ∈ {True, False}.
        Accumulates a virtual-evidence factor the next query will apply."""
        if difficulty not in P_CORRECT:
            raise ValueError(f"unknown question difficulty: {difficulty}")
        p_c = P_CORRECT[difficulty]  # per-state P(correct | mastery)
        if correct:
            likelihood = [p_c["none"], p_c["partial"], p_c["mastered"]]
        else:
            likelihood = [1 - p_c["none"], 1 - p_c["partial"], 1 - p_c["mastered"]]
        # Temperature flattens the likelihood before it becomes evidence.
        # Algebraically equivalent to treating one answer as 1/τ answers.
        tau = max(self.temperature, 1e-6)
        if tau != 1.0:
            likelihood = [x ** (1.0 / tau) for x in likelihood]
        # Normalise into a valid CPD (pgmpy's virtual_evidence expects a
        # distribution; proportional likelihood is what matters).
        total = sum(likelihood) or 1.0
        likelihood = [x / total for x in likelihood]
        factor = TabularCPD(
            variable=topic_id,
            variable_card=3,
            values=[[p] for p in likelihood],
            state_names={topic_id: STATES},
        )
        self._virtual_evidence.append(factor)
        self._history.append({
            "topic_id": topic_id,
            "difficulty": difficulty,
            "correct": correct,
        })

    def reset(self, topic_id: str, cascading: bool = False) -> None:
        """Forget virtual evidence tied to a topic.

        - isolated: drop observations on that topic only.
        - cascading: drop observations on that topic AND on its descendants,
          forcing downstream beliefs back to the prior-propagation state.
        """
        if not cascading:
            self._virtual_evidence = [
                f for f in self._virtual_evidence if f.variable != topic_id
            ]
            self._history = [
                h for h in self._history if h["topic_id"] != topic_id
            ]
            return
        descendants = {topic_id} | set(
            self._get_descendants(topic_id)
        )
        self._virtual_evidence = [
            f for f in self._virtual_evidence if f.variable not in descendants
        ]
        self._history = [
            h for h in self._history if h["topic_id"] not in descendants
        ]

    def _get_descendants(self, topic_id: str) -> set[str]:
        # pgmpy's BN graph is networkx-compatible
        import networkx as nx
        return nx.descendants(self.bn, topic_id)

    # --- inference ----------------------------------------------------------

    def marginal(self, topic_id: str) -> dict[str, float]:
        """Posterior distribution over mastery for one topic."""
        q = self._infer.query(
            variables=[topic_id],
            virtual_evidence=self._virtual_evidence or None,
            show_progress=False,
        )
        return dict(zip(STATES, q.values.tolist()))

    def marginals(self) -> dict[str, dict[str, float]]:
        """Marginal posterior for every topic in the network."""
        out: dict[str, dict[str, float]] = {}
        for tid in self.topic_ids:
            out[tid] = self.marginal(tid)
        return out

    def entropy(self, topic_id: str) -> float:
        from math import log
        m = self.marginal(topic_id)
        return -sum(p * log(p) for p in m.values() if p > 0)

    def history(self) -> list[dict]:
        return list(self._history)


# ----------------------------------------------------------------------------
# CLI sanity check
# ----------------------------------------------------------------------------

def _print_summary(tm: TutorModel) -> None:
    print(f"Network: {len(tm.topic_ids)} nodes, "
          f"{tm.bn.number_of_edges()} edges")
    print()
    print("Prior marginals (no evidence):")
    for tid in tm.topic_ids:
        m = tm.marginal(tid)
        title = tm.title(tid)
        tier = tm.tier(tid)
        bar = (
            f"n={m['none']:.2f}  p={m['partial']:.2f}  m={m['mastered']:.2f}"
        )
        print(f"  {tid:18s} [{tier:6s}] {bar}  | {title}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", type=int, default=1)
    args = ap.parse_args()
    tm = TutorModel.from_graph(chapter=args.chapter)
    _print_summary(tm)
    if not tm.topic_ids:
        raise SystemExit("Empty graph.")
    root_id = tm.topic_ids[0]
    leaf_id = tm.topic_ids[-1]
    print()
    print(f"--- Observing: correct on medium question for {root_id} ---")
    tm.observe(root_id, difficulty="medium", correct=True)
    m_root = tm.marginal(root_id)
    print(f"  {root_id} posterior: n={m_root['none']:.3f} "
          f"p={m_root['partial']:.3f} m={m_root['mastered']:.3f}")
    m_leaf = tm.marginal(leaf_id)
    print(f"  {leaf_id} ({tm.title(leaf_id)}) posterior: "
          f"n={m_leaf['none']:.3f} p={m_leaf['partial']:.3f} "
          f"m={m_leaf['mastered']:.3f}")
