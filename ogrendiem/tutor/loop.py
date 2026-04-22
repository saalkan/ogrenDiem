"""Placement test + tutoring loop for the vertical slice.

Exposes two entry-points:

  run_placement(tm, max_questions)    — drive an adaptive placement test
  run_tutoring(tm, n_steps)           — drive the 4-step per-topic loop

Both take a `TutorModel` (the pgmpy wrapper) and an `AnswerSource` callable
that, given a Question, returns (correct: bool). The callable abstracts
whether answers come from a human CLI or a simulated student.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Callable

from pgm.model import TutorModel
from tutor.questions import Difficulty, Question, generate_question

AnswerSource = Callable[[Question], bool]


# ----------------------------------------------------------------------------
# Utility metrics over belief state
# ----------------------------------------------------------------------------

def _entropy(dist: dict[str, float]) -> float:
    return -sum(p * log(p) for p in dist.values() if p > 0)


def total_entropy(tm: TutorModel) -> float:
    return sum(_entropy(tm.marginal(tid)) for tid in tm.topic_ids)


def frontier_score(tm: TutorModel, tid: str) -> float:
    """Higher = better next-topic candidate.

    Prefer topics where
        · mastery is uncertain (high entropy — room to learn *and* worth asking),
        · and prerequisites are relatively high (ready to be taught).

    Earlier version multiplied by (1 - mastery) which caused us to re-teach
    topics the placement test had already established as mastered, because
    "mastery" was just a point estimate and always left some weight on the
    not-mastered states.  Using entropy resolves this: a confidently-mastered
    topic contributes no score.
    """
    m = tm.marginal(tid)
    # Uncertainty in mastery
    from math import log
    uncertainty = -sum(p * log(p) for p in m.values() if p > 0)

    parents = list(tm.bn.get_parents(tid))
    if parents:
        parent_mastery = sum(
            tm.marginal(p)["mastered"] + 0.5 * tm.marginal(p)["partial"]
            for p in parents
        ) / len(parents)
    else:
        parent_mastery = 1.0  # roots are always "ready"
    return uncertainty * parent_mastery


# ----------------------------------------------------------------------------
# Topic selection
# ----------------------------------------------------------------------------

def select_placement_topic(tm: TutorModel, seen: set[str]) -> str | None:
    """Pick the highest-entropy topic we haven't already asked about."""
    best: tuple[float, str] | None = None
    for tid in tm.topic_ids:
        if tid in seen:
            continue
        h = _entropy(tm.marginal(tid))
        if best is None or h > best[0]:
            best = (h, tid)
    return best[1] if best else None


def select_tutoring_topic(tm: TutorModel, completed: set[str]) -> str | None:
    """Pick the best frontier topic, breaking ties by lower difficulty
    and shallower depth."""
    scored: list[tuple[float, int, int, str]] = []
    for tid in tm.topic_ids:
        if tid in completed:
            continue
        node = tm.nodes[tid]
        scored.append((
            -frontier_score(tm, tid),       # minimise negative → maximise score
            node["difficulty_level"],
            node.get("depth", 0),
            tid,
        ))
    if not scored:
        return None
    scored.sort()
    return scored[0][3]


# ----------------------------------------------------------------------------
# Placement test
# ----------------------------------------------------------------------------

@dataclass
class PlacementResult:
    questions_asked: int
    final_entropy: float
    history: list[dict]


def run_placement(
    tm: TutorModel,
    answer_source: AnswerSource,
    max_questions: int = 8,
    entropy_floor: float = 0.25,  # nats/topic; below the prior, so we always
                                  # ask at least a few questions
    min_delta: float = 0.05,      # stop when a question moves total_H < delta
) -> PlacementResult:
    """Adaptive placement: probe highest-entropy topics with medium-difficulty
    diagnostics until confidence is high or returns diminish.

    `entropy_floor` is interpreted in nats per topic; stop if
    total_entropy / n_topics < entropy_floor.
    """
    seen: set[str] = set()
    n_topics = len(tm.topic_ids)
    prev_total = total_entropy(tm)
    history: list[dict] = [{"event": "start", "total_entropy": prev_total}]

    for step in range(1, max_questions + 1):
        tid = select_placement_topic(tm, seen)
        if tid is None:
            break
        topic = tm.nodes[tid]
        q = generate_question(topic, "medium")
        correct = answer_source(q)
        tm.observe(tid, difficulty="medium", correct=correct)
        seen.add(tid)

        now = total_entropy(tm)
        delta = prev_total - now
        history.append({
            "event": "question",
            "step": step,
            "topic_id": tid,
            "correct": correct,
            "total_entropy": now,
            "delta": delta,
        })

        if now / n_topics < entropy_floor:
            history.append({"event": "stop", "reason": "entropy-floor"})
            break
        if step >= 3 and delta < min_delta:
            history.append({"event": "stop", "reason": "diminishing-returns"})
            break
        prev_total = now

    return PlacementResult(
        questions_asked=sum(1 for h in history if h.get("event") == "question"),
        final_entropy=total_entropy(tm),
        history=history,
    )


# ----------------------------------------------------------------------------
# Tutoring loop — 4-step teaching sequence per topic
# ----------------------------------------------------------------------------

TEACH_SEQUENCE: list[tuple[str, Difficulty | None]] = [
    ("teach", None),      # trivial example with answer shown (stub: just print)
    ("quiz", "easy"),
    ("quiz", "medium"),
    ("quiz", "hard"),
]


def teach_topic(tm: TutorModel, tid: str, answer_source: AnswerSource) -> list[dict]:
    topic = tm.nodes[tid]
    events: list[dict] = []
    for step, diff in TEACH_SEQUENCE:
        if step == "teach":
            events.append({
                "event": "teach",
                "topic_id": tid,
                "title": topic["title"],
                "content": topic.get("description", "")[:400],
            })
            continue
        q = generate_question(topic, diff)  # type: ignore[arg-type]
        correct = answer_source(q)
        tm.observe(tid, difficulty=diff, correct=correct)  # type: ignore[arg-type]
        events.append({
            "event": "quiz",
            "topic_id": tid,
            "difficulty": diff,
            "correct": correct,
        })
    return events


def run_tutoring(
    tm: TutorModel,
    answer_source: AnswerSource,
    n_topics: int = 4,
) -> list[dict]:
    completed: set[str] = set()
    all_events: list[dict] = []
    for _ in range(n_topics):
        tid = select_tutoring_topic(tm, completed)
        if tid is None:
            break
        events = teach_topic(tm, tid, answer_source)
        completed.add(tid)
        all_events.append({
            "topic_id": tid,
            "title": tm.title(tid),
            "events": events,
            "posterior": tm.marginal(tid),
        })
    return all_events
