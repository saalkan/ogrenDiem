"""Interactive CLI tutor.

You play the student. The PGM updates after every answered question and
you can inspect beliefs, skip, reset, or jump to any topic at any prompt.

Usage:
    python -m tutor.cli                 # resume if a saved session exists
    python -m tutor.cli --new           # start fresh (ignores save file)
    python -m tutor.cli --save path.json

State is persisted as the *list of observations*, not the posterior
distributions. On resume we rebuild a fresh TutorModel and replay every
observation — this way the saved file stays small and stays in sync with
the current network topology.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from math import log
from pathlib import Path

from pgm.model import TutorModel
from tutor.loop import (
    TEACH_SEQUENCE,
    select_placement_topic,
    select_tutoring_topic,
    total_entropy,
)
from tutor.questions import Question, generate_question

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_ROOT = ROOT / "data" / "processed"


def default_save(chapter: int) -> Path:
    return PROCESSED_ROOT / f"ch{chapter}" / "session.json"


# ----------------------------------------------------------------------------
# Persistence — replay observations on a fresh model
# ----------------------------------------------------------------------------

def save_state(tm: TutorModel, path: Path) -> None:
    payload = {
        "history": tm.history(),
        "completed": sorted(
            {h["topic_id"] for h in tm.history()
             if h.get("difficulty") == "hard" and h.get("correct") is not None}
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_state(path: Path, chapter: int) -> tuple[TutorModel, set[str]]:
    tm = TutorModel.from_graph(chapter=chapter)
    completed: set[str] = set()
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        for h in payload.get("history", []):
            tm.observe(h["topic_id"], h["difficulty"], h["correct"])
        completed = set(payload.get("completed", []))
    return tm, completed


# ----------------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------------

def _bar(p: float, width: int = 12) -> str:
    filled = int(round(p * width))
    return "█" * filled + "·" * (width - filled)


def _fmt_marg(m: dict[str, float]) -> str:
    return (
        f"none {_bar(m['none'])} {m['none']:.2f}  "
        f"partial {_bar(m['partial'])} {m['partial']:.2f}  "
        f"mastered {_bar(m['mastered'])} {m['mastered']:.2f}"
    )


def _argmax_label(m: dict[str, float]) -> str:
    return max(m, key=lambda k: m[k])


def print_header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def print_topic_summary(tm: TutorModel, tid: str) -> None:
    node = tm.nodes[tid]
    m = tm.marginal(tid)
    print(f"  {tid}  [§{node['parent_section_num']} · "
          f"D{node['difficulty_level']} {node['difficulty_tier']}]  "
          f"{node['title']}")
    print(f"    belief: {_fmt_marg(m)}  →  {_argmax_label(m)}")


def print_all_marginals(tm: TutorModel) -> None:
    print_header("Current belief state (all topics)")
    by_sec: dict[str, list[str]] = {}
    for tid in tm.topic_ids:
        by_sec.setdefault(tm.nodes[tid]["parent_section_num"], []).append(tid)
    for sec in sorted(by_sec, key=lambda s: [int(x) for x in s.split(".")]):
        print(f"\n  § {sec}")
        for tid in by_sec[sec]:
            print_topic_summary(tm, tid)
    print()


# ----------------------------------------------------------------------------
# Prompts
# ----------------------------------------------------------------------------

_HELP = (
    "\nCommands at any prompt:\n"
    "  1-5       answer the question\n"
    "  s         skip this question (no evidence recorded)\n"
    "  t         skip the rest of this topic\n"
    "  r         reset a topic (you'll be asked which and whether cascading)\n"
    "  m         show current belief state for all topics\n"
    "  j         jump to a specific topic\n"
    "  h         help\n"
    "  q         save and quit\n"
)


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return "q"


def prompt_answer(q: Question) -> str:
    """Render the question and read one command.

    Returns the raw command string (the caller interprets it).
    """
    print()
    print(f"  Topic: {q.topic_id}   ·   Difficulty: {q.difficulty}")
    print(f"  Q: {q.question}")
    for i, opt in enumerate(q.options, start=1):
        print(f"    {i}) {opt}")
    return ask("\n  Answer [1-5, s/t/r/m/j/h/q]: ")


def prompt_pick_topic(tm: TutorModel) -> str | None:
    print_header("Jump to topic")
    for i, tid in enumerate(tm.topic_ids, start=1):
        print(f"  {i:2d}) {tid:18s}  {tm.nodes[tid]['title']}")
    raw = ask("\n  Pick a number (or blank to cancel): ")
    if not raw:
        return None
    try:
        idx = int(raw) - 1
        return tm.topic_ids[idx]
    except (ValueError, IndexError):
        print("  invalid choice")
        return None


def prompt_reset(tm: TutorModel) -> None:
    tid = prompt_pick_topic(tm)
    if tid is None:
        return
    mode = ask(f"  Reset {tid} — (i)solated or (c)ascading? [i/c]: ")
    cascading = mode.startswith("c")
    tm.reset(tid, cascading=cascading)
    kind = "cascading" if cascading else "isolated"
    print(f"  Reset {kind}. {tid} beliefs restored to prior.")


# ----------------------------------------------------------------------------
# Teaching a single topic — the 4-step sequence
# ----------------------------------------------------------------------------

@dataclass
class StepResult:
    quit: bool = False
    skipped_topic: bool = False


def teach_step_show(tm: TutorModel, tid: str) -> StepResult:
    """Step 1 of the teach sequence: trivial teaching moment."""
    node = tm.nodes[tid]
    print()
    print(f"  🟢 Teaching example for: {node['title']}")
    print()
    print(f"  {node.get('description', '').replace(chr(10), chr(10) + '  ')}")
    print()
    cmd = ask("  Press enter to continue, or [t/r/m/j/h/q]: ")
    return _dispatch_side_command(cmd, tm, tid)


def teach_step_quiz(tm: TutorModel, tid: str, difficulty: str) -> StepResult:
    """Steps 2-4: easy / medium / hard MCQ."""
    topic = tm.nodes[tid]
    q = generate_question(topic, difficulty)  # type: ignore[arg-type]
    while True:
        cmd = prompt_answer(q)
        if cmd in {"1", "2", "3", "4", "5"}:
            idx = int(cmd) - 1
            correct = idx == q.correct_index
            tm.observe(tid, difficulty=difficulty, correct=correct)
            tag = "✓ correct" if correct else "✗ incorrect"
            print(f"\n  {tag}.  {q.explanation}")
            m = tm.marginal(tid)
            print(f"  New belief: {_fmt_marg(m)}")
            return StepResult()
        side = _dispatch_side_command(cmd, tm, tid)
        if side.quit or side.skipped_topic or cmd == "s":
            if cmd == "s":
                print("  (skipped — no evidence recorded)")
            return side


def _dispatch_side_command(cmd: str, tm: TutorModel, current_tid: str | None) -> StepResult:
    """Handle the non-answer commands. Returns whether to quit or skip topic.
    Unknown commands are a no-op (caller will re-prompt)."""
    if cmd == "q":
        return StepResult(quit=True)
    if cmd == "t":
        return StepResult(skipped_topic=True)
    if cmd == "h":
        print(_HELP)
    elif cmd == "m":
        print_all_marginals(tm)
    elif cmd == "r":
        prompt_reset(tm)
    elif cmd == "j":
        new = prompt_pick_topic(tm)
        if new is not None and new != current_tid:
            # A "jump" during teaching is really just: abandon the current
            # topic and let the outer loop re-pick. We signal by skipping.
            print(f"  Jumping to {new}.  (Current topic abandoned.)")
            return StepResult(skipped_topic=True)
    return StepResult()


def teach_topic(tm: TutorModel, tid: str) -> StepResult:
    print_header(f"Topic: {tm.nodes[tid]['title']}")
    print_topic_summary(tm, tid)

    # Step 1: teaching moment
    r = teach_step_show(tm, tid)
    if r.quit or r.skipped_topic:
        return r

    # Steps 2-4: quizzes at easy / medium / hard
    for _, diff in TEACH_SEQUENCE[1:]:
        r = teach_step_quiz(tm, tid, diff)  # type: ignore[arg-type]
        if r.quit or r.skipped_topic:
            return r
    return StepResult()


# ----------------------------------------------------------------------------
# Placement test — CLI-driven
# ----------------------------------------------------------------------------

def run_placement_cli(
    tm: TutorModel,
    max_questions: int = 8,
    entropy_floor: float = 0.25,
) -> bool:
    """Return True if the user quit mid-placement."""
    print_header("Placement test")
    print(
        "  We'll ask a handful of medium-difficulty diagnostic questions to\n"
        "  estimate what you already know. The system picks the most uncertain\n"
        "  topic each step.\n"
    )
    n_topics = len(tm.topic_ids)
    seen: set[str] = set()
    for step in range(1, max_questions + 1):
        tid = select_placement_topic(tm, seen)
        if tid is None:
            break
        per_topic_H = total_entropy(tm) / n_topics
        print(f"\n  [placement {step}/{max_questions}]  "
              f"overall uncertainty: {per_topic_H:.3f} nats/topic")
        print_topic_summary(tm, tid)
        q = generate_question(tm.nodes[tid], "medium")
        while True:
            cmd = prompt_answer(q)
            if cmd in {"1", "2", "3", "4", "5"}:
                idx = int(cmd) - 1
                correct = idx == q.correct_index
                tm.observe(tid, difficulty="medium", correct=correct)
                tag = "✓ correct" if correct else "✗ incorrect"
                print(f"  {tag}.")
                break
            if cmd == "s":
                print("  (skipped)")
                break
            side = _dispatch_side_command(cmd, tm, tid)
            if side.quit:
                return True
            if side.skipped_topic:
                break
        seen.add(tid)
        if total_entropy(tm) / n_topics < entropy_floor:
            print("\n  Placement done — uncertainty low enough.")
            break
    return False


# ----------------------------------------------------------------------------
# Main tutoring loop
# ----------------------------------------------------------------------------

def run_tutoring_cli(tm: TutorModel, completed: set[str]) -> bool:
    """Return True if user quit."""
    print_header("Tutoring")
    print(
        "  I'll pick a frontier topic for you to study, then run through a\n"
        "  4-step sequence: teaching example → easy MCQ → medium MCQ → hard MCQ.\n"
        "  After each answer, beliefs propagate across the whole graph.\n"
    )
    while True:
        tid = select_tutoring_topic(tm, completed)
        if tid is None:
            print("\n  No frontier topics left — you're done!")
            return False
        r = teach_topic(tm, tid)
        if r.quit:
            return True
        if r.skipped_topic:
            # don't add to completed so frontier selector may pick it again later
            continue
        completed.add(tid)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chapter", type=int, default=1,
                        help="Chapter number to tutor (default: 1). "
                             "Each chapter has its own graph and save file; "
                             "state never leaks across chapters.")
    parser.add_argument("--save", type=Path, default=None,
                        help="path to session JSON "
                             "(default: data/processed/ch<N>/session.json)")
    parser.add_argument("--new", action="store_true",
                        help="ignore any existing save and start fresh")
    args = parser.parse_args(argv)

    save_path: Path = args.save or default_save(args.chapter)
    if args.new and save_path.exists():
        save_path.unlink()

    tm, completed = load_state(save_path, args.chapter)
    resumed = bool(tm.history())

    print_header(f"Adaptive Precalculus Tutor — Chapter {args.chapter}")
    if resumed:
        print(f"  Resumed session from {save_path}")
        print(f"  {len(tm.history())} prior observations, "
              f"{len(completed)} topics completed")
    else:
        print("  Fresh session.")
    print(_HELP)

    try:
        if not resumed:
            quit_now = run_placement_cli(tm)
            if not quit_now:
                quit_now = run_tutoring_cli(tm, completed)
        else:
            quit_now = run_tutoring_cli(tm, completed)
    finally:
        save_state(tm, save_path)
        print(f"\n  Session saved to {save_path}")

    print_all_marginals(tm)


if __name__ == "__main__":
    main()
