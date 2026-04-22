"""End-to-end validation via a *simulated student*.

Rather than asking a human, we give each topic an oracle mastery level
(none / partial / mastered) and use the observation model P_CORRECT
to sample answers. We then run placement + tutoring and print how
beliefs evolve — the PGM should pull each topic's posterior toward
its oracle mastery.

Usage:
    python -m tutor.simulate

Scenarios:
    - strong-early:  mastered on 1.1–1.2, none further
    - uniform-partial:  partial on every topic
    - polarised:     mastered on 1.1, none elsewhere (stress test)
"""
from __future__ import annotations

import random
from typing import Callable

from pgm.cpts import P_CORRECT, STATES
from pgm.model import TutorModel
from tutor.loop import (
    PlacementResult,
    run_placement,
    run_tutoring,
    total_entropy,
)
from tutor.questions import Question


def make_oracle_answerer(
    oracle: dict[str, str],
    rng: random.Random,
) -> Callable[[Question], bool]:
    """Return an answer_source that uses oracle mastery + P_CORRECT to
    sample a correct/incorrect answer for each question."""
    def answer(q: Question) -> bool:
        true_state = oracle.get(q.topic_id, "none")
        p_c = P_CORRECT[q.difficulty][true_state]
        return rng.random() < p_c
    return answer


# ----------------------------------------------------------------------------
# Scenarios
# ----------------------------------------------------------------------------

def scenario_strong_early(topic_ids: list[str]) -> dict[str, str]:
    oracle: dict[str, str] = {}
    for tid in topic_ids:
        sec = int(tid.split("_s")[1].split("_")[0])
        oracle[tid] = "mastered" if sec <= 2 else "none"
    return oracle


def scenario_uniform_partial(topic_ids: list[str]) -> dict[str, str]:
    return {tid: "partial" for tid in topic_ids}


def scenario_polarised(topic_ids: list[str]) -> dict[str, str]:
    # Master only the very first topic in the chapter, leave the rest at none.
    first = topic_ids[0] if topic_ids else None
    return {tid: ("mastered" if tid == first else "none") for tid in topic_ids}


SCENARIOS = {
    "strong-early":    scenario_strong_early,
    "uniform-partial": scenario_uniform_partial,
    "polarised":       scenario_polarised,
}


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------

def _fmt_marg(m: dict[str, float]) -> str:
    return f"n={m['none']:.2f} p={m['partial']:.2f} m={m['mastered']:.2f}"


def _agreement(posterior: dict[str, float], true_state: str) -> str:
    # "argmax" label for posterior
    arg = max(posterior, key=lambda k: posterior[k])
    ok = "✓" if arg == true_state else "✗"
    return f"pred={arg:8s} true={true_state:8s} {ok}"


def run_scenario(name: str, chapter: int = 1, rng_seed: int = 42) -> None:
    print(f"\n{'=' * 78}")
    print(f"Scenario: {name}  (chapter {chapter})")
    print("=" * 78)

    tm = TutorModel.from_graph(chapter=chapter)
    oracle = SCENARIOS[name](tm.topic_ids)
    rng = random.Random(rng_seed)
    answer = make_oracle_answerer(oracle, rng)

    # Placement
    h0 = total_entropy(tm) / len(tm.topic_ids)
    print(f"Initial per-topic entropy: {h0:.3f}")
    pr = run_placement(tm, answer, max_questions=8)
    print(f"Placement asked {pr.questions_asked} questions, "
          f"final per-topic entropy: {pr.final_entropy / len(tm.topic_ids):.3f}")

    # Tutoring loop — 4 frontier topics
    events = run_tutoring(tm, answer, n_topics=4)
    print(f"Tutored {len(events)} topics:")
    for ev in events:
        m = ev["posterior"]
        tid = ev["topic_id"]
        print(f"  {tid:18s} {_fmt_marg(m)}   {ev['title']}")

    # Agreement summary across all topics
    print()
    print("Per-topic argmax vs oracle:")
    agreeing = 0
    for tid in tm.topic_ids:
        m = tm.marginal(tid)
        true_state = oracle[tid]
        arg = max(m, key=lambda k: m[k])
        if arg == true_state:
            agreeing += 1
        print(f"  {tid:18s} {_fmt_marg(m)}   {_agreement(m, true_state)}  "
              f"| {tm.title(tid)}")
    print(f"\nArgmax agreement: {agreeing}/{len(tm.topic_ids)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--chapter", type=int, default=1)
    ap.add_argument("--scenario", choices=sorted(SCENARIOS) + ["all"], default="all")
    args = ap.parse_args()
    names = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for name in names:
        run_scenario(name, chapter=args.chapter)
