"""Question-generation interface.

For the vertical slice we only ship a *stub* generator: it emits mock
questions from topic metadata so the tutoring loop can be validated
end-to-end without an LLM.

The public surface is `generate_question(topic, difficulty)` returning a
dict with fields {question, options, correct_index, explanation, difficulty,
topic_id}. When we plug in a real LLM later (Gemma / OpenAI / local), it
just needs to satisfy this same contract.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, asdict
from typing import Literal

Difficulty = Literal["easy", "medium", "hard"]


@dataclass
class Question:
    topic_id: str
    difficulty: Difficulty
    question: str
    options: list[str]
    correct_index: int
    explanation: str

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------------
# Stub generator
# ----------------------------------------------------------------------------

_TEMPLATES: dict[Difficulty, list[str]] = {
    "easy": [
        "Which of the following best describes the core idea of \"{title}\"?",
        "In the context of {title}, which statement is most accurate?",
    ],
    "medium": [
        "A student is asked to apply the concept of {title}. Which step is correct?",
        "Given a routine problem involving {title}, which approach is valid?",
    ],
    "hard": [
        "Consider a non-trivial case of {title}. Which reasoning is correct?",
        "Combining {title} with its prerequisites, which conclusion follows?",
    ],
}


def _distractors(concept_pool: list[str], k: int) -> list[str]:
    pool = [c for c in concept_pool if len(c) > 2]
    random.shuffle(pool)
    base = pool[:k] if len(pool) >= k else pool + [f"unrelated idea {i}" for i in range(k - len(pool))]
    return [f"A statement primarily about '{b}'" for b in base]


def generate_question(topic: dict, difficulty: Difficulty, seed: int | None = None) -> Question:
    """Return a stub 5-option MCQ for the given topic + difficulty.

    `topic` must include: topic_id, title, concepts, description.
    """
    rng = random.Random(seed if seed is not None else f"{topic['topic_id']}|{difficulty}")
    title = topic.get("title", "this topic")
    concepts = topic.get("concepts", [])[:]
    rng.shuffle(concepts)

    template = rng.choice(_TEMPLATES[difficulty])
    stem = template.format(title=title)

    correct = (
        f"The canonical idea behind '{title}': "
        f"{topic.get('description', '') or title}."
    )[:220]

    # 4 distractors, each referencing an unrelated concept-ish phrase
    dist_pool = (
        topic.get("concepts", [])
        + [f"topic {i}" for i in range(4)]
    )
    distractors = _distractors(
        [c for c in dist_pool if c.lower() not in title.lower()],
        4,
    )

    options = distractors + [correct]
    rng.shuffle(options)
    correct_index = options.index(correct)

    explanation = (
        f"The correct option restates the definition or core notion of "
        f"'{title}'. The other options describe unrelated concepts."
    )

    return Question(
        topic_id=topic["topic_id"],
        difficulty=difficulty,
        question=stem,
        options=options,
        correct_index=correct_index,
        explanation=explanation,
    )
