# ogrendiem — Adaptive Precalculus Tutor

Vertical slice of a Koller-Friedman-style adaptive tutor built on a Bayesian
network overlaid on a precalculus prerequisite graph.

**Slice scope:** Chapter 1 ("Functions") of Lippman & Rasmussen's *Precalculus:
An Investigation of Functions* (LibreTexts).

## Pipeline

1. `scraper/` — fetch chapter pages from LibreTexts, cache as JSON
2. `nlp/` — extract topics, concepts, prerequisite edges
3. `graph/` — build and validate NetworkX DAG; export to Kùzu
4. `pgm/` — define pgmpy Bayesian network with templated CPTs
5. `tutor/` — CLI placement test + tutoring loop for validation

## Layout

```
scraper/   — Step 1
nlp/       — Step 2
graph/     — Step 3
pgm/       — Step 4
tutor/     — Step 5 (CLI for slice; mobile UI comes later)
data/
  raw/       — scraped JSON per page
  processed/ — topics, edges, serialized graph
```

## Source

https://math.libretexts.org/Bookshelves/Precalculus/Book%3A_Precalculus__An_Investigation_of_Functions_(Lippman_and_Rasmussen)

Licensed CC-BY-NC-SA. All derived content preserves attribution.
