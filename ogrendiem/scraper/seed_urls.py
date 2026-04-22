"""Seed URLs for the scraper, organised by chapter.

Each chapter gets its own entry in `CHAPTERS`. Downstream stages
(extract / build / model / cli) all operate on *one chapter at a time* —
topics, graphs, and belief states from different chapters are kept fully
separate so cross-chapter structural edges can't accidentally be inferred.

Add a new chapter by listing its section URLs here, then run the pipeline
with `--chapter N`.
"""

BOOK_ROOT = (
    "https://math.libretexts.org/Bookshelves/Precalculus/"
    "Book%3A_Precalculus__An_Investigation_of_Functions_(Lippman_and_Rasmussen)"
)

CHAPTERS: dict[int, list[str]] = {
    1: [
        f"{BOOK_ROOT}/01%3A_Functions/1.01%3A_Functions_and_Function_Notation",
        f"{BOOK_ROOT}/01%3A_Functions/1.02%3A_Domain_and_Range",
        f"{BOOK_ROOT}/01%3A_Functions/1.03%3A_Rates_of_Change_and_Behavior_of_Graphs",
        f"{BOOK_ROOT}/01%3A_Functions/1.04%3A_Composition_of_Functions",
        f"{BOOK_ROOT}/01%3A_Functions/1.05%3A_Transformation_of_Functions",
        f"{BOOK_ROOT}/01%3A_Functions/1.06%3A_Inverse_Functions",
    ],
    2: [
        f"{BOOK_ROOT}/02%3A_Linear_Functions/2.01%3A_Linear_Functions",
        f"{BOOK_ROOT}/02%3A_Linear_Functions/2.02%3A_Graphs_of_Linear_Functions",
        f"{BOOK_ROOT}/02%3A_Linear_Functions/2.03%3A_Modeling_with_Linear_Functions",
        f"{BOOK_ROOT}/02%3A_Linear_Functions/2.04%3A_Fitting_Linear_Models_to_Data",
        f"{BOOK_ROOT}/02%3A_Linear_Functions/2.05%3A_Absolute_Value_Functions",
    ],
    # Chapter 3 on LibreTexts has a trailing dot in the chapter path segment.
    3: [
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.01%3A_Power_Functions",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.02%3A_Quadratic_Functions",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.03%3A_Graphs_of_Polynomial_Functions",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.04%3A_Factor_Theorem_and_Remainder_Theorem",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.05%3A_Real_Zeros_of_Polynomials",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.06%3A_Complex_Zeros",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.07%3A_Rational_Functions",
        f"{BOOK_ROOT}/03%3A_Polynomial_and_Rational_Functions./3.08%3A_Inverses_and_Radical_Functions",
    ],
    4: [
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.01%3A_Exponential_Functions",
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.02%3A_Graphs_of_Exponential_Functions",
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.03%3A_Logarithmic_Functions",
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.04%3A_Logarithmic_Properties",
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.05%3A_Graphs_of_Logarithmic_Functions",
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.06%3A_Exponential_and_Logarithmic_Models",
        f"{BOOK_ROOT}/04%3A_Exponential_and_Logarithmic_Functions/4.07%3A_Fitting_Exponential_Models_to_Data",
    ],
    5: [
        f"{BOOK_ROOT}/05%3A_Trigonometric_Functions_of_Angles/5.01%3A_Circles",
        f"{BOOK_ROOT}/05%3A_Trigonometric_Functions_of_Angles/5.02%3A_Angles",
        f"{BOOK_ROOT}/05%3A_Trigonometric_Functions_of_Angles/5.03%3A_Points_on_Circles_Using_Sine_and_Cosine",
        f"{BOOK_ROOT}/05%3A_Trigonometric_Functions_of_Angles/5.04%3A_The_Other_Trigonometric_Functions",
        f"{BOOK_ROOT}/05%3A_Trigonometric_Functions_of_Angles/5.05%3A_Right_Triangle_Trigonometry",
    ],
    6: [
        f"{BOOK_ROOT}/06%3A_Periodic_Functions/6.01%3A_Sinusoidal_Graphs",
        f"{BOOK_ROOT}/06%3A_Periodic_Functions/6.02%3A_Graphs_of_the_Other_Trig_Functions",
        f"{BOOK_ROOT}/06%3A_Periodic_Functions/6.03%3A_Inverse_Trigonometric_Functions",
        f"{BOOK_ROOT}/06%3A_Periodic_Functions/6.04%3A_Solving_Trigonometric_Equations",
        f"{BOOK_ROOT}/06%3A_Periodic_Functions/6.05%3A_Modeling_with_Trigonometric_Functions",
    ],
    7: [
        f"{BOOK_ROOT}/07%3A_Trigonometric_Equations_and_Identities/7.01%3A_Solving_Trigonometric_Equations_with_Identities",
        f"{BOOK_ROOT}/07%3A_Trigonometric_Equations_and_Identities/7.02%3A_Addition_and_Subtraction_Identities",
        f"{BOOK_ROOT}/07%3A_Trigonometric_Equations_and_Identities/7.03%3A_Double_Angle_Identities",
        f"{BOOK_ROOT}/07%3A_Trigonometric_Equations_and_Identities/7.04%3A_Modeling_Changing_Amplitude_and_Midline",
    ],
    8: [
        f"{BOOK_ROOT}/08%3A_Further_Applications_of_Trigonometry/8.01%3A_Non-Right_Triangles_-_Laws_of_Sines_and_Cosines",
        f"{BOOK_ROOT}/08%3A_Further_Applications_of_Trigonometry/8.02%3A_Polar_Coordinates",
        f"{BOOK_ROOT}/08%3A_Further_Applications_of_Trigonometry/8.03%3A_Polar_Form_of_Complex_Numbers",
        f"{BOOK_ROOT}/08%3A_Further_Applications_of_Trigonometry/8.04%3A_Vectors",
        f"{BOOK_ROOT}/08%3A_Further_Applications_of_Trigonometry/8.05%3A_Dot_Product",
        f"{BOOK_ROOT}/08%3A_Further_Applications_of_Trigonometry/8.06%3A_Parametric_Equations",
    ],
    9: [
        f"{BOOK_ROOT}/09%3A_Conics/9.01%3A_Ellipses",
        f"{BOOK_ROOT}/09%3A_Conics/9.02%3A_Hyperbolas",
        f"{BOOK_ROOT}/09%3A_Conics/9.03%3A_Parabolas_and_Non-Linear_Systems",
        f"{BOOK_ROOT}/09%3A_Conics/9.04%3A_Conics_in_Polar_Coordinates",
    ],
}


def chapter_url(ch: int) -> str:
    """URL for the chapter index page (used for display only)."""
    return f"{BOOK_ROOT}/{ch:02d}%3A_Functions"


# ----------------------------------------------------------------------------
# Groups — named bundles of chapters that share a DAG and a tutoring session.
# Chapters within a group are ordered as listed; cross-chapter structural
# edges follow that order.
# ----------------------------------------------------------------------------

GROUPS: dict[str, list[int]] = {
    "1":       [1],
    "1-2-3-4": [1, 2, 3, 4],
    "1-5-6-7": [1, 5, 6, 7],
    "1-3-8-9": [1, 3, 8, 9],
}


def scope_label(chapters: list[int]) -> str:
    """Canonical directory/label for a chapter or group.

    - Single chapter → 'chN' (matches the raw/processed ch-per-chapter layout).
    - Multiple chapters → 'gA-B-C' (e.g. 'g1-2-3-4').
    """
    if len(chapters) == 1:
        return f"ch{chapters[0]}"
    return "g" + "-".join(str(c) for c in chapters)


def chapters_for(spec: str) -> list[int]:
    """Resolve a CLI spec into a chapter list.

    Accepts:
      - a single digit like '2'      → [2]
      - a GROUPS label like '1-5-6-7' → GROUPS[label]
      - a dash-joined ad-hoc list    → [int(x) for x in spec.split('-')]
    """
    if spec in GROUPS:
        return list(GROUPS[spec])
    if spec.isdigit():
        return [int(spec)]
    return [int(x) for x in spec.split("-")]


# Backwards compatibility for any direct consumers.
SECTION_URLS = CHAPTERS[1]
