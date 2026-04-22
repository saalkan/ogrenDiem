# öğrenDiem — Architecture, Math, and Logic

A deep, source-linked explanation of what the app is, how it models a
student, how the pieces fit, and why each decision was made. Readers:
reviewers, future developers, and the future-self porting this to a
real backend.

---

## 1. The product thesis, in one paragraph

A precalculus student's difficulty is rarely "this topic" in isolation —
it's that a prerequisite somewhere upstream is shaky, and that shakiness
compounds. öğrenDiem ingests a real textbook (Lippman & Rasmussen,
LibreTexts), extracts an explicit prerequisite DAG, fits a Bayesian
Knowledge-Tracing model per topic, and uses the DAG to *propagate* what
one answer tells us about neighbouring topics. The student sees a
gamified "collect emojis as you master topics" surface; the backing
system is a probabilistic graphical model they never have to look at.

Four design axes set everything downstream:

1. **Event-sourced truth.** Every student action is an append-only event;
   the UI state is a *derived projection* that can be rebuilt from the log.
2. **One swap point.** The UI depends on a `TutorEngine` interface;
   `LocalEngine` (today) and a future `RemoteEngine` are interchangeable.
3. **Content is shape-identical across engines.** Bundled JSON today,
   the same shape served by a FastAPI backend tomorrow.
4. **Determinism in the build pipeline.** Emoji assignment, tree slots,
   cave positions, and cluster IDs are computed once by Python and baked
   into JSON — the app is a pure consumer of content, never a generator.

---

## 2. System-wide architecture

### 2.1 The four layers

```
┌───────────────────────────────────────────────────────────────┐
│  Python build pipeline      (offline, runs a few times/year)  │
│  ──────────────────────────────────────────────────────────── │
│  LibreTexts → topic/edge extraction → DAG build →             │
│  parallelism clustering → export_mobile.py →                  │
│  assets/data/{topics, graph, clusters, questions}.json        │
└───────────────────────────────────────────────────────────────┘
                              │   (build-time bundled JSON)
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  Engine layer                (TutorEngine interface)          │
│  ─────────────────────────────────────────────────────────    │
│  LocalEngine  ──  BKT + noisy-AND + replay + frontier         │
│                    AsyncStorage event log                     │
│  (swap) RemoteEngine → HTTP → FastAPI → pgmpy on the server   │
└───────────────────────────────────────────────────────────────┘
                              │   (TutorEngine methods)
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  State / store layer         (Zustand)                        │
│  ─────────────────────────────────────────────────────────    │
│  studentId + cached DerivedState + refresh after every write  │
└───────────────────────────────────────────────────────────────┘
                              │   (selectors)
                              ▼
┌───────────────────────────────────────────────────────────────┐
│  UI layer                    (React Native + Expo)            │
│  ─────────────────────────────────────────────────────────    │
│  Garden · Cave · Learn · Progress   (four tabs)               │
│  Tree · Cave · EmojiNode · QuestionCard · MathView (5 comps)  │
└───────────────────────────────────────────────────────────────┘
```

Each layer only talks *down* to the layer beneath it:

- UI imports from `@/store/tutor` (and for read-only bundled data, from
  `@/data/bundled`), never from `@/engine`.
- Store calls `engine.*` through `@/engine` (a one-line re-export).
- Engine reads bundled data and writes to AsyncStorage.
- The build pipeline never runs in the app.

### 2.2 The single swap point

`src/engine/index.ts` is literally:

```ts
import { LocalEngine } from './local';
import type { TutorEngine } from '@/shared/api';
export const engine: TutorEngine = new LocalEngine();
```

When a backend exists:

```ts
import { RemoteEngine } from './remote';
export const engine: TutorEngine = new RemoteEngine(process.env.EXPO_PUBLIC_API!);
```

Nothing else changes. The `TutorEngine` interface in `src/shared/api.ts`
is the contract both implementations honour.

### 2.3 Why event-sourced

A `DerivedState` (mastery + stash + picked per topic) is never persisted.
What persists is the append-only `LogEvent[]`. To get current state, we
`replay(log)`. This buys three things:

- **Provable determinism.** Same log → same state, always. Useful for
  debugging "why did my mastery do that?".
- **Parameter changes are free.** Tune `pLearn` → replay → all historical
  students get re-scored correctly.
- **Backend sync is trivial.** POST new events, pull missing events,
  replay. No conflict resolution, no CRDTs.

The cost is O(n) replay per read. For a demo with <1000 events per
student that's ~1 ms. If it ever matters, checkpoint every N events.

---

## 3. The content pipeline (Python side)

### 3.1 From textbook to DAG

`ogrendiem/graph/build.py` (not part of the app, upstream) extracts
topics from the LibreTexts HTML — one topic per numbered example or
sub-concept. Edges come from two sources:

- **Explicit prose cues.** "Recall that…", "As in Section 1.2…", plus
  typed marker phrases the extractor recognizes.
- **Co-occurrence in prerequisite lists.** Many sections state their
  prereqs at the top; the extractor parses them.

Each edge carries a `strength` ∈ (0,1] and a `source` tag
(`"prose"` | `"prereq-list"` | `"manual"`). The app uses the binary
"edge exists" signal; strengths are reserved for a later weighted
noisy-AND.

### 3.2 Clusters

`ogrendiem/graph/parallelism.py` runs a community-detection pass on the
undirected projection of the DAG, restricted to scope (g1-3-8-9). The
algorithm is Louvain (networkx `community.louvain_communities`) at a
resolution tuned so that 50–60 topics yield 4–6 clusters. Output: a
list of `cluster_id → [topic_id]` sets.

Cluster titles are synthesized as `"<first topic title> / <last topic title>"`
for the demo — a stopgap until an LLM-authored title step is added.

### 3.3 Deterministic emoji + layout baking

`ogrendiem/graph/export_mobile.py` is the single source of truth for:

- **Emoji assignment.** `sha256(topic_id).digest_int % len(pool)` picks
  from `GARDEN_POOL` (40 flowers/fruits) and `CAVE_POOL` (40
  animals/crystals). Deterministic means the *same* student seeing the
  *same* topic next year sees the *same* strawberry.
- **Garden slots.** `branch = section_index_within_chapter`, and
  `u ∈ [0.25, 0.95]` is seeded from `sha256(topic_id + "u")` so topics
  are spread along the branch without collisions.
- **Cave slots.** `networkx.spring_layout` on the within-cluster
  subgraph, then min-max normalized into `(x, y) ∈ [0.08, 0.92]²`.
- **Cluster colors.** Cycled from a 10-color palette tuned for dark UI.

These four files are the entire contract between Python and JS:

```
assets/data/topics.json      55 topics × ~12 fields
assets/data/graph.json       {nodes: [...], edges: [...]}
assets/data/clusters.json    {clusters: [{cluster_id, title, color, topic_ids}]}
assets/data/questions.json   30 hand-curated worked examples
```

### 3.4 Questions

Current bundle: 30 items, 10 topics × 3 roles (recognize, apply, vary).
Each is a `Question` (see §5.2) with LaTeX-formatted prompt and
step-by-step solution. Origin is `"bundled"`. The schema also admits
`"llm-generated"` for the future on-demand path (§8).

---

## 4. The math: how a single answer moves the world

### 4.1 Bayesian Knowledge Tracing (BKT)

BKT (Corbett & Anderson, 1995) models "does the student know this skill?"
as a latent binary variable `K ∈ {known, ¬known}` with four parameters:

| Parameter | Symbol | Default | Meaning |
|---|---|---|---|
| prior known | `P(K₀)` | 0.05 | belief before first observation |
| learn rate | `p_learn` | 0.25 | `P(¬known → known)` per attempt |
| slip | `p_slip` | 0.10 | `P(wrong \| known)` |
| guess | `p_guess` | 0.20 | `P(correct \| ¬known)` |
| forget | `p_forget` | 0.00 | `P(known → ¬known)` per attempt |

Given prior `p = P(K)` and an observation `o ∈ {correct, wrong}`, the
update is two steps — **evidence** then **transition**:

**Evidence (Bayes' rule):**

```
P(o | K)    = 1 - p_slip    if o = correct
            =     p_slip    if o = wrong

P(o | ¬K)   =     p_guess   if o = correct
            = 1 - p_guess   if o = wrong

P(K | o) = P(o | K) · p
           ────────────────────────────────────
           P(o | K) · p  +  P(o | ¬K) · (1 - p)
```

**Transition (one attempt of learning opportunity):**

```
P(K') = P(K | o) · (1 - p_forget) + (1 - P(K | o)) · p_learn
```

Implementation: [`src/engine/bkt.ts:28`](src/engine/bkt.ts). Clamped to
`[0.001, 0.999]` to avoid degenerate 0/1 states that can't move.

**Worked example.** Student answers their first question on a topic
correctly:

```
prior            = 0.05
P(o=✓ | K)       = 0.90
P(o=✓ | ¬K)      = 0.20
posterior        = 0.90 · 0.05 / (0.90·0.05 + 0.20·0.95)
                 = 0.045 / (0.045 + 0.190)
                 = 0.1915
P(K')            = 0.1915 · 1 + 0.8085 · 0.25
                 = 0.1915 + 0.2021
                 = 0.3936
```

Mastery jumps from 0.05 → 0.39 on a single correct. Two more correct
answers push it past 0.80 (the frontier threshold). This is the
"mastery bar visibly moves" demo beat.

### 4.2 Noisy-AND prerequisite propagation

BKT gives us *local* mastery per topic. But a student's real readiness
for topic T depends on its prerequisites too: you can't really "know"
composition of functions if you don't know function evaluation. We
combine local mastery with prereq ability via **noisy-AND**:

```
ability(T) = localMastery(T) · ∏ ability(p)   for p ∈ parents(T)
```

This is recursive. A leaf topic (no parents) has `ability = local`.
A topic with one unmastered parent has its ability capped by that
parent. A topic with *all* parents at ability 1 has `ability = local`.

Implementation: [`src/engine/propagate.ts:18`](src/engine/propagate.ts),
memoized so it's O(N + E) per pass.

**Why noisy-AND and not a weighted sum.** Prerequisites are
conjunctive in math: missing *any* one tanks the whole thing. A sum
would let a strong parent mask a weak parent; a product will not.
The noisy form (via the BKT posteriors already in `[0,1]`) handles
uncertainty gracefully — unknown parents make you less confident about
the descendant in proportion.

**Observation: propagation is read-only.** We never write propagated
mastery back to the BKT state. `mastery[t]` is always the *local*
posterior; `ability[t]` is computed on demand for frontier decisions
and for the propagation-delta reported back to the UI. This keeps the
event-sourced invariant clean: the log alone determines every number.

### 4.3 Frontier selection

A topic is on the **frontier** iff:

1. its local mastery is `< MASTERY_THRESHOLD` (0.80), AND
2. every in-scope parent's *ability* is `≥ MASTERY_THRESHOLD`.

Frontier topics are sorted by `(depth asc, difficulty asc)` so the
recommender prefers shallower, easier items when multiple are
simultaneously ready.

Implementation: [`src/engine/local.ts:68`](src/engine/local.ts). The
`getNextTopic` call returns `frontier[0]` or `null` if everything in
scope is mastered.

This is the whole "adaptive path" story: the engine always picks the
next topic that is (a) actionable (prereqs met) and (b) still worth
working on (not yet mastered). No search, no RL, no magic — just a
gate on a topologically-layered graph.

### 4.4 The parameters, and why these defaults

| Param | Value | Rationale |
|---|---|---|
| `P(K₀) = 0.05` | Precalc is post-high-school; most topics start *unknown*. Not 0 because students occasionally pre-know. |
| `p_learn = 0.25` | Classic BKT literature hovers 0.1–0.4; 0.25 makes three correct answers move mastery past 0.80 — good demo pacing. |
| `p_slip = 0.10` | "Careless error" rate on a known skill. |
| `p_guess = 0.20` | Matches a 5-choice MCQ; for free-response this could be lower. |
| `p_forget = 0` | Within-session decay is negligible; add when sessions span days. |
| `MASTERY_THRESHOLD = 0.80` | Defensible by convention (80% in BKT-SR literature) and it aligns demo intuitions. |

These are tunable in `src/engine/bkt.ts` and replay makes tuning safe.

---

## 5. Data model

### 5.1 Core types (`src/shared/types.ts`)

```ts
Topic {
  topic_id, title,
  parent_chapter_num, parent_section_num, parent_section,
  position_in_section, difficulty_level, difficulty_tier,
  depth, description,
  garden_emoji, cave_emoji,
  garden_slot: { branch, u },
  cave_slot: { cluster, x, y },
  cluster_id
}

Edge     { from, to, source, strength }
Cluster  { cluster_id, title, color, topic_ids }
```

`depth` is the DAG depth (longest path from a root); used for sorting
the frontier and for per-chapter rollups in Progress.

### 5.2 Question schema

```ts
Question {
  question_id, topic_id,
  role:   'recognize' | 'apply' | 'vary' | 'trap' | 'integrate',
  tier:   'easy' | 'medium' | 'hard',
  prompt: string,        // LaTeX in $...$ / $$...$$
  solution_steps: string[],
  answer: string,
  checks: string[],      // plausible correct student tokens (future auto-grade)
  origin: 'bundled' | 'llm-generated',
}
```

Roles encode *item function* (not difficulty); tiers encode difficulty.
See `src/llm-prompts/system.md` for the discipline that must hold in
every item.

### 5.3 Events (the append-only log)

```ts
AnswerEvent { t: 'answer', ts, student_id, question_id, topic_id, correct, time_ms }
PickEvent   { t: 'pick',   ts, student_id, topic_id, emoji, area }
```

These two are the only mutations the system produces. Everything on
screen is a projection of the sequence.

### 5.4 Derived state

```ts
DerivedState {
  mastery: Record<TopicId, number>    // BKT posterior (local, not propagated)
  stash:   Record<TopicId, number>    // collectable emojis waiting
  picked:  Record<TopicId, number>    // lifetime emojis collected
}
```

- `mastery` is *local* — always compute `ability(t)` with
  `abilityMap(mastery)` when propagation matters.
- `stash` / `picked` are the gamification layer and are decoupled from
  mastery (see §6.2 for why).

---

## 6. UI / interaction logic

### 6.1 The four tabs — mapping to tutor modes

| Tab | Mode | Scope | Main artifact |
|---|---|---|---|
| Garden | Mode 1 — **chapter** | `{kind:'chapter', key: '1'|'3'|'8'|'9'}` | `Tree` per chapter |
| Cave | Mode 3 — **cluster** | `{kind:'cluster', key: '0..4'}` | `Cave` per cluster |
| Learn | any | typically `'group'` | `QuestionCard` list |
| Progress | Mode 2 — **group** | `{kind:'group', key:'g1-3-8-9'}` | rollup bars + rows |

Garden and Cave are two *views of the same underlying DAG*. Trees group
topics by chapter/section (useful for "where in the book am I?"). Caves
group topics by prerequisite cluster (useful for "which skills cluster
together?"). Two mental models, one model underneath.

### 6.2 The collection loop (stash & pick)

Why emojis? A mastery bar alone is abstract. A physical thing you can
*collect* makes progress tangible. The rule:

- Correct answer on topic `t` → `stash[t] += 1`.
- Tap a ripe emoji in Garden or Cave → `stash[t] -= 1`, `picked[t] += 1`.
- Long-press a node → navigate to Learn for `t` (the "open topic" gesture).

`EmojiNode` renders three visual states from `(stash, picked)`:

| state | condition | look |
|---|---|---|
| bare | `stash = 0, picked = 0` | greyed silhouette |
| ripe | `stash > 0` | full colour + green count badge |
| harvested | `stash = 0, picked > 0` | muted + grey lifetime badge |

Crucially, **picking does not change mastery**. A student can mastery-max
a topic and still have 0 picked (they never tapped). A student can keep
answering correctly and accumulate stash without ever picking. The loop
is a reward surface, not the model. This matters because the model must
remain auditable from the answer events alone.

### 6.3 Tree layout math (Garden)

`src/components/Tree.tsx` draws a trunk and N branches in an SVG, where
N = (max `branch` index used in the chapter) + 1. Each branch is a
cubic Bézier with control points chosen to alternate left/right:

```ts
p0 = (trunkX, y0)                       // attach to trunk
p1 = (trunkX + side·W·0.15, y0 - 20)    // initial curl
p2 = (trunkX + side·W·0.35, y0 - 60)    // mid arc
p3 = (trunkX + side·W·0.42, y0 - 90)    // tip
```

Each emoji's pixel position is
`bezier(p0, p1, p2, p3, u)` with `u` coming from `garden_slot.u`. The
trunk itself is a single S-curve Bézier. Emoji views are absolutely
positioned on top of the SVG — React Native SVG's text layout is
limited, so interactive elements are native Views.

### 6.4 Cave layout math

`src/components/Cave.tsx` normalizes `cave_slot.(x,y)` into the view's
pixel rectangle with 28-px padding. Edges inside the cluster are drawn
as quadratic Bézier "tunnels" with a midpoint lifted 18px for a subtle
arch. Background is a radial gradient (darker at the edges) — the
"cave chamber" feel without doing 3D.

### 6.5 Math rendering (`MathView`)

`react-native-webview` loads KaTeX (0.16.9) via jsDelivr CDN and
auto-renders `$...$` / `$$...$$` delimiters. Height is measured on
document ready and posted back to RN via
`window.ReactNativeWebView.postMessage(height)`. The parent sets
`height = reportedHeight`, and lives inside a *single* RN `ScrollView`.

Why this pattern:

- One scroll container per screen — no nested scroll jank.
- The WebView is `scrollEnabled={false}`; it acts like a native block.
- Heights settle in two ticks (60 ms, 250 ms) to catch font loading.

### 6.6 Question flow (`QuestionCard`)

A deliberate "reveal → self-grade" flow:

1. Prompt shown immediately.
2. "Show next step" reveals `solution_steps[i]` one at a time.
3. "Reveal answer" shows the final answer.
4. "I got it ✓" or "Not yet" → `recordAnswer(topic, question, correct, elapsed)`.

Self-grading is a scoping decision, not an oversight: auto-grading
free-response math is a research project. The `question.checks` tokens
are already there so a future `CheckedAnswerCard` can land without a
schema change.

---

## 7. State management (Zustand)

### 7.1 Store shape (`src/store/tutor.ts`)

```ts
TutorStore {
  studentId:   StudentId | null
  derived:     DerivedState
  setStudentId(id)
  refresh(): Promise<void>                            // engine.getDerived → set({derived})
  recordAnswer(topicId, questionId, correct, timeMs)  // engine.recordAnswer + refresh
  recordPick(topicId, emoji, area)                    // engine.recordPick   + refresh
}
```

Two rules the codebase follows:

1. **UI never calls the engine directly.** UI imports store actions.
   This means swapping engines doesn't ripple into components.
2. **Every write refreshes.** After appending to the log, we recompute
   the full `DerivedState` and re-render. It's wasteful in theory but
   correct by construction, and the replay is cheap.

### 7.2 Persistence (`src/store/persist.ts`)

AsyncStorage keys:

- `ogrendiem:student_id` — a UUID (created on first launch).
- `ogrendiem:log:<student_id>` — JSON array of `LogEvent`.

`appendEvent` reads the log, pushes, writes it back. Not atomic under
concurrent writes, but the app has a single actor (the user) so it's
safe in practice. A future upgrade: SQLite via `expo-sqlite` with
append-only INSERTs.

### 7.3 Bootstrap (`src/store/bootstrap.ts`)

```ts
useBootstrap():
  read or create student_id
  set in store
  engine.getDerived(sid) → set derived
  mark ready
```

`App.tsx` returns `null` until `ready`. No splash screen; the data
loads fast enough (~50 ms on a phone).

---

## 8. Local vs Remote engine — the swap path

`TutorEngine` methods, organized by what a future server must return:

| Method | Server responsibility |
|---|---|
| `getTopics / getGraph / getClusters` | Static content; serve from DB, cache aggressively. |
| `getDerived(sid)` | Load events for `sid`, replay (same algorithm as JS), return state. |
| `getFrontier / getNextTopic` | Derived state + frontier selection, pagination optional. |
| `getQuestions(topicId, n)` | Fetch from the two-tier cache (bundled + LLM-generated). |
| `requestMoreQuestions(topicId, role, n)` | If cache miss: call LLM with `worked-example.md`, validate with `questionBatchSchema`, persist, return. |
| `recordAnswer / recordPick` | Append event to per-student log, return updated derived slice. |
| `exportEventLog / importEventLog` | Device ↔ server sync channel. |

Because `LocalEngine` already has `replay` and the full algebra, the
server can be "`LocalEngine`'s Python twin" — pgmpy for Bayes, plus a
thin FastAPI layer. This is *the* reason the JS and Python
implementations stay in lockstep.

---

## 9. Why these choices, in a sentence each

- **Expo (not bare RN).** One command launches on Android, iOS, and web;
  zero native config during the demo window.
- **TypeScript strict.** The DAG/BKT math is small but fiddly; strict
  catches half the bugs before the simulator does.
- **Zustand (not Redux).** Two selectors and two actions; Redux is overkill.
- **AsyncStorage (not SQLite yet).** Ship a demo, not a database.
- **KaTeX via CDN (not MathJax native).** WebView + KaTeX is 20 lines;
  a native math renderer is a project.
- **SVG for Tree/Cave (not Skia/Canvas).** SVG is declarative, paints
  crisply at any DPR, and works on web unchanged.
- **Bundled questions.** A demo needs guaranteed correctness; LLM paths
  need review loops we don't have yet.
- **Event log as ground truth.** Cheap today, essential for sync tomorrow.

---

## 10. Invariants to preserve

If you hack on this code, do not break these without thinking hard:

1. **`DerivedState` is never persisted.** Log-only is the invariant.
2. **`mastery[t]` is always the local BKT posterior**, never the
   propagated ability. Compute ability on demand.
3. **Every write refreshes `derived`.** One source of truth on screen.
4. **UI components import from `@/data/bundled` and `@/store`, never
   `@/engine`.** The swap point is sacred.
5. **JSON schemas in `assets/data/*.json` match `shared/types.ts` exactly.**
   The Python exporter is the only writer to those files.
6. **Question JSON entries with `origin: 'llm-generated'` must pass
   `questionBatchSchema`** before they hit the bundle.

---

## 11. Extension points (how each future feature slots in)

| Feature | Where it plugs in |
|---|---|
| Spaced repetition / decay | Set `p_forget > 0` in `bkt.ts`; add a `ReviewEvent` time-bucketed replay step. |
| Auto-grading | `QuestionCard` consumes `question.checks`; add a normalized token matcher. |
| New chapters | Rerun Python pipeline with a wider scope; JSON regenerates; UI chapter chips pick them up. |
| LLM-generated questions | Implement `RemoteEngine.requestMoreQuestions`; server calls LLM with `worked-example.md`, validates with `questionBatchSchema`, caches. |
| Cross-device sync | `exportEventLog` ↔ server POST; `importEventLog` merges on login. |
| Teacher view | New screen reading the same `DerivedState` for a list of students. |
| Richer propagation | Use `edge.strength` as a weight: `ability(T) = local · ∏ ability(p)^w(p)`. |

Every one of these is a change in one or two files, not a rewrite.

---

## 12. Glossary

- **BKT** — Bayesian Knowledge Tracing; 4-parameter HMM for "does student know this skill?".
- **DAG** — Directed Acyclic Graph; the prerequisite structure of topics.
- **Noisy-AND** — probabilistic AND: `P(A ∧ B) ≈ P(A) · P(B)` under independence.
- **Frontier** — set of topics with all prereqs mastered but not yet mastered themselves.
- **Scope** — a filter on topics: chapter / cluster / group.
- **Event log** — append-only sequence of `AnswerEvent | PickEvent`.
- **Derived state** — `{mastery, stash, picked}`, a pure function of the log.
- **Ability** — propagated mastery: `local · ∏ parent-abilities`.
- **Stash** — collectable emojis on a node, awaiting a tap.
- **Picked** — lifetime collected emojis (never decrements).

---

## 13. The one-line summary for a hallway conversation

> A textbook is a DAG; a student is a distribution over that DAG; a lesson
> is an observation that updates the distribution; the UI is a projection
> of that distribution into two metaphors — a tree you harvest and a cave
> you explore.
