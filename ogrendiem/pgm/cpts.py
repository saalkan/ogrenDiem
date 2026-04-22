"""CPT templates for the precalculus PGM.

States and tables exactly as specified in the project brief:

Root-node priors (difficulty-tier-specific, no prerequisites):
    easy     [none=0.33, partial=0.33, mastered=0.34]   (0.33 + 0.33 + 0.34, normalised)
    medium   [none=0.40, partial=0.40, mastered=0.20]
    hard     [none=0.60, partial=0.30, mastered=0.10]

Single-prerequisite CPTs (row = parent state, col = child state):
    easy topics    rows for prereq ∈ {none, partial, mastered}
                   [0.95, 0.04, 0.01]
                   [0.45, 0.35, 0.20]
                   [0.33, 0.33, 0.34]
    medium topics  [0.95, 0.04, 0.01]
                   [0.60, 0.30, 0.10]
                   [0.40, 0.40, 0.20]
    hard topics    [0.97, 0.025, 0.005]
                   [0.75, 0.20, 0.05]
                   [0.55, 0.30, 0.15]

Multi-prerequisite: noisy-AND — each parent contributes an independent
factor drawn from the single-prereq CPT row for its state, and the child
distribution is the element-wise product of those factors (renormalised).
A single weak parent can still suppress mastery, but two strong parents
reinforce each other rather than collapsing to the minimum.

Observation model  P(correct | mastery, question-difficulty) — slip/guess
rates from published BKT literature. 0.20 is the 5-choice MCQ guess floor;
the mastered column is (1 − slip) with slip growing with difficulty.
    easy     none=0.20  partial=0.85  mastered=0.97   (slip=0.03)
    medium   none=0.20  partial=0.60  mastered=0.93   (slip=0.07)
    hard     none=0.20  partial=0.35  mastered=0.90   (slip=0.10)
"""
from __future__ import annotations

STATES = ["none", "partial", "mastered"]
STATE_INDEX = {s: i for i, s in enumerate(STATES)}


def _norm(row: list[float]) -> list[float]:
    s = sum(row)
    return [x / s for x in row]


# ----- Priors (root nodes) --------------------------------------------------

PRIOR = {
    "easy":   _norm([0.33, 0.33, 0.34]),
    "medium": _norm([0.40, 0.40, 0.20]),
    "hard":   _norm([0.60, 0.30, 0.10]),
}


# ----- Single-prereq CPTs  row = parent state -------------------------------

SINGLE_PREREQ_CPT = {
    "easy": {
        "none":     _norm([0.95, 0.04, 0.01]),
        "partial":  _norm([0.45, 0.35, 0.20]),
        "mastered": _norm([0.33, 0.33, 0.34]),
    },
    "medium": {
        "none":     _norm([0.95, 0.04, 0.01]),
        "partial":  _norm([0.60, 0.30, 0.10]),
        "mastered": _norm([0.40, 0.40, 0.20]),
    },
    "hard": {
        "none":     _norm([0.97, 0.025, 0.005]),
        "partial":  _norm([0.75, 0.20, 0.05]),
        "mastered": _norm([0.55, 0.30, 0.15]),
    },
}


# ----- Observation model ----------------------------------------------------

P_CORRECT = {
    "easy":   {"none": 0.20, "partial": 0.85, "mastered": 0.97},
    "medium": {"none": 0.20, "partial": 0.60, "mastered": 0.93},
    "hard":   {"none": 0.20, "partial": 0.35, "mastered": 0.90},
}


def weakest_link(parent_states: tuple[str, ...]) -> str:
    """Return the state with the smallest index in STATES across parents.

    Retained for reference / fallback; `child_row` uses noisy-AND."""
    return min(parent_states, key=lambda s: STATE_INDEX[s])


def child_row(tier: str, parent_states: tuple[str, ...]) -> list[float]:
    """P(child | parents) under noisy-AND aggregation.

    Each parent contributes an independent factor equal to the single-prereq
    CPT row for its state; the child distribution is the element-wise product
    of those factors, renormalised. With one parent this reduces exactly to
    the single-prereq CPT. With multiple parents, "mastered" survives only
    when every parent supports it, but two strong parents reinforce each
    other (unlike weakest-link, which would collapse to the min)."""
    if not parent_states:
        return PRIOR[tier]
    tier_cpt = SINGLE_PREREQ_CPT[tier]
    combined = [1.0, 1.0, 1.0]
    for s in parent_states:
        row = tier_cpt[s]
        combined = [c * r for c, r in zip(combined, row)]
    total = sum(combined)
    if total <= 0:
        # degenerate (shouldn't happen with the tables above) — fall back
        return tier_cpt[weakest_link(parent_states)]
    return [c / total for c in combined]
