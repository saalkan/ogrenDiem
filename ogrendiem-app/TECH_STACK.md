# öğrenDiem — Tools & Libraries

A one-page-per-layer explanation of every dependency this project uses:
what it does, why it was chosen, what it replaces, and where it shows up
in the codebase. Grouped by layer.

---

## 1. JavaScript runtime & build

### Node.js (≥ 18)
JavaScript runtime that executes the Metro bundler, the Expo CLI, and
`tsc --noEmit`. No app code runs in Node — the app runs in the React
Native JS engine (Hermes) on device. Node is only here because the
toolchain is JS-native.

### npm
Package manager. Chosen over pnpm/yarn because it ships with Node and
reviewers won't need to install a second tool. Lock file
`package-lock.json` pins transitive versions.

### TypeScript (~5.3)
Strict-mode type checker. We use it for three things the codebase
actually depends on:

- **Discriminated unions** for `LogEvent = AnswerEvent | PickEvent`
  so the replay switch is exhaustive.
- **Path aliases** (`@/*` → `src/*`) configured in `tsconfig.json` and
  resolved by Metro via `babel.config.js`.
- **Contract enforcement** between the `TutorEngine` interface and both
  `LocalEngine` and the future `RemoteEngine` — a missing method is a
  compile error, not a runtime surprise.

### Babel (`@babel/core`) + `babel-preset-expo`
Transpiles modern JS/TS/JSX down to what Hermes executes. Nothing
custom here — we use Expo's preset unchanged.

### Metro
React Native's bundler (the JS equivalent of Webpack). Bundles every
`import`, including JSON — this is how `assets/data/*.json` becomes
available via `import topicsJson from '../../assets/data/topics.json'`
in `src/data/bundled.ts`. JSON is resolved at build time, so changes
require a Metro restart.

---

## 2. Mobile platform

### Expo SDK 51 (managed workflow)
Expo is a layer on top of React Native that provides:

- **A single `npm start`** that prints a QR and lets Expo Go run the app.
- **Pre-compiled native modules** so we never open Xcode or Android
  Studio during development.
- **Cross-platform identity**: same code on iOS, Android, and web.

We stay "managed" (no `expo prebuild`) because every native library we
need is included in Expo's compatible list. If we later need a native
module Expo doesn't ship, we'd switch to a development build — zero JS
code changes.

### React Native 0.74.5
The mobile app framework. RN lets you write UI in React (components,
state, hooks) and renders to native views (UIView/UIKit on iOS,
android.view.View on Android). We use it because:

- The student audience is mobile-first.
- Web fallback exists for projection/presentation scenarios.
- The ecosystem has everything we need (SVG, WebView, AsyncStorage).

### React 18.2
The component model underneath RN. Hooks (`useState`, `useEffect`,
`useMemo`) are the only React surface we use; no class components, no
Suspense, no concurrent features (RN's concurrent support is immature).

### Expo Go (the runtime app on the phone)
A phone app that loads any Expo project over the network. During demos
this is what the QR code opens. It is not a dependency in `package.json` —
it's installed from the App Store / Play Store on the target device.

### `expo-status-bar`
One component, one purpose: style the OS status bar (light content on
our dark UI). Included because doing it manually on Android requires a
theme XML edit we want to avoid.

### `react-native-safe-area-context`
Provides the `SafeAreaProvider` wrapping `App.tsx`. Gives children
access to device-specific insets (notch, home indicator) so content
doesn't hide under them. Used implicitly by `@react-navigation/native`.

### `react-native-screens`
Swaps React Navigation's JS screen containers for native container
primitives (`UINavigationController` / `Fragment`). Faster transitions
and less memory. Required by `@react-navigation/*`.

---

## 3. Navigation

### `@react-navigation/native`
The core of React Navigation. Provides `NavigationContainer`, the theme
system (`NavTheme` in `App.tsx`), deep linking, and the navigator API.
Chosen because it's the de-facto standard and has drop-in Expo support.

### `@react-navigation/bottom-tabs`
The bottom tab navigator used in `src/navigation/RootTabs.tsx`. Four
tabs (Garden / Cave / Learn / Progress) map to the four tutor modes.
Each tab renders a screen via `<Tab.Screen component={...} />`.

---

## 4. State management

### Zustand (`^4.5`)
A minimal store: `create<T>()` returns a hook. Used exclusively in
`src/store/tutor.ts` to hold `studentId` and `derived: DerivedState`.

Why Zustand over alternatives:

| Alternative | Why not |
|---|---|
| Redux | Boilerplate-heavy for two actions and two selectors. |
| Context | Re-renders everything on every update. |
| MobX | Proxy-based reactivity is overkill; harder to audit. |
| Recoil / Jotai | Fine choices, but Zustand's selector API is simpler. |

Zustand fits because our state is small, writes are infrequent (one per
answer/pick), and the selector-based `useTutor((s) => s.derived.stash)`
pattern gives automatic subscription granularity.

### `@react-native-async-storage/async-storage`
The RN port of `localStorage`: a key/value store that's async and
promise-based. Used in `src/store/persist.ts` for two keys:

- `ogrendiem:student_id` — UUID minted on first launch.
- `ogrendiem:log:<student_id>` — JSON array of `LogEvent[]`.

Reasonable choice for a demo (<1000 events). For production, swap for
`expo-sqlite` with an append-only `events` table to avoid read-modify-write
on every append.

### Zod (`^3.23`)
A runtime schema validator with TS type inference. Used in
`src/llm-prompts/schema.ts` to validate LLM-emitted `Question` batches
before they enter the cache. Compile-time TS types catch developer
errors; Zod catches model-output errors.

Example:
```ts
questionBatchSchema.parse(JSON.parse(llmReply));
// throws if any field is missing, wrong type, or length<2
```

---

## 5. Rendering

### `react-native-svg` (15.2)
SVG primitives (`<Svg>`, `<Path>`, `<G>`, `<Rect>`, `<Defs>`,
`<RadialGradient>`). Used in:

- `src/components/Tree.tsx` — trunk + branches as cubic Béziers.
- `src/components/Cave.tsx` — cave chamber background + in-cluster
  tunnels as quadratic Béziers.

Why SVG over Canvas/Skia:

- Declarative, matches React's mental model.
- Identical rendering on native and web.
- Crisp at any device pixel ratio.
- No shader compilation cost at startup.

### `react-native-webview` (13.8)
Full browser engine-in-a-view. The *only* place we use it is
`src/components/MathView.tsx`, where we host KaTeX to render LaTeX.

Why a WebView for math:

- Native math text rendering in RN requires a commercial SDK or
  hand-rolling a font layout.
- KaTeX is battle-tested, fast, and has excellent coverage of precalc
  notation.
- The WebView is sandboxed; nothing on the page can touch app state
  except via `postMessage`.

Pattern: the HTML measures its own rendered height and posts it back;
the parent sets `height` so the WebView behaves like a native block
inside a regular `ScrollView`. No nested scroll.

### KaTeX (loaded from jsDelivr CDN, inside the WebView)
LaTeX-to-HTML math renderer by Khan Academy. Not an npm dep — loaded
at runtime from:

```
cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css
cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js
cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js
```

`auto-render` scans the DOM for `$...$` and `$$...$$` delimiters.
After the first successful load the WebView caches the files; offline
launches work unless you clear the WebView cache. Future work: bundle
KaTeX as a local asset for true airplane-mode guarantees.

---

## 6. Python content pipeline (`ogrendiem/requirements.txt`)

The Python side runs *offline*, produces the four JSON files in
`assets/data/`, and never ships to the phone. But the app would not
exist without it.

### NetworkX (`>= 3.2`)
Graph library. Used for:

- Storing the prerequisite DAG (`nx.DiGraph`).
- BFS/DFS for depth computation.
- `nx.spring_layout` for cave node positions (force-directed).
- `nx.community.louvain_communities` for cluster discovery in
  `graph/parallelism.py`.

Why NetworkX: pure Python, ubiquitous in research, the algorithms we
need are one import away. Performance is irrelevant at this scale
(55 nodes, 140 edges).

### pgmpy (`>= 0.1.25`)
Probabilistic Graphical Models in Python. The *reference
implementation* of the Bayesian network: Conditional Probability Tables
(CPTs) with noisy-AND, BKT per topic, and inference via belief
propagation. Lives in `ogrendiem/pgm/`.

The **JavaScript engine (`src/engine/`) is a faithful port** of the
pgmpy math — same parameters, same update formulas, same propagation
rule. Why a port and not pgmpy-on-server-only:

- A demo without network dependency is more robust on conference Wi-Fi.
- Replay is cheap in JS; same-algorithm parity lets us verify the port
  by feeding the same event log through both and comparing outputs.
- Future `RemoteEngine` uses pgmpy server-side for richer inference
  (variable elimination, not just per-topic BKT); the JS fallback stays
  correct for solo mode.

### NumPy (transitive via pgmpy / scikit-learn)
Array math. Not called directly in our code but pulled in by the
probabilistic stack.

### scikit-learn (`>= 1.4`)
Used in `ogrendiem/nlp/` for TF-IDF and clustering during topic
deduplication at build time. Not used in the app or engine directly.

### spaCy (`>= 3.7`)
NLP pipeline for extracting topics from textbook prose. Tokenization,
lemmatization, and noun-phrase chunking to pull topic names out of
LibreTexts HTML. Lives in `ogrendiem/nlp/`. Not touched at runtime.

### requests / BeautifulSoup4 / lxml
HTTP client + HTML parser + fast XML backend. Used only in
`ogrendiem/scraper/` to fetch LibreTexts chapters. Scraping is a
one-shot operation; results are cached under `precalc_db/`.

### Kùzu (`>= 0.6`)
Embedded graph database. Used as an intermediate store for the
normalized DAG in `ogrendiem/precalc_db/`. Not a runtime dependency of
the app — the export pipeline reads from Kùzu and writes to JSON.

Why Kùzu over SQLite: graph queries (ancestors, descendants, transitive
closure) are one-liners in Cypher-like syntax and much clearer than
recursive CTEs.

### Matplotlib (`>= 3.8`)
2D/3D plotting. Powers `graph/visualize_3d.py` and
`graph/visualize_3d_clusters.py` — the 3D DAG visualizations shown in
the demo deck. Not on the phone.

### pyvis (`>= 0.3`)
Interactive HTML network visualizations. Exports the DAG to a
standalone HTML file for browsing during development. Not on the phone.

---

## 7. Content & services

### LibreTexts — *Precalculus* by Lippman & Rasmussen
The textbook. Creative Commons licensed, which is why we can ingest,
restructure, and cite it. Scraped once into `ogrendiem/precalc_db/`,
transformed into topics/edges, then abandoned at runtime.

### An LLM (any chat model, future work)
Not a current runtime dependency. `src/llm-prompts/` contains the
templates (`system.md`, `worked-example.md`) and the Zod validator for
when `RemoteEngine` is built. The app has never made an LLM call; the
30 bundled questions were LLM-drafted and hand-reviewed, then baked as
`origin: 'bundled'`.

---

## 8. Versions summary (the "if anyone asks" table)

| Layer | Tool | Version | Role |
|---|---|---|---|
| Runtime | Node.js | ≥ 18 | toolchain host |
| Build | TypeScript | ~5.3 | type safety |
| Build | Babel preset | babel-preset-expo | transpile |
| Build | Metro | (bundled w/ Expo) | JS bundler |
| Platform | Expo SDK | ~51.0 | cross-platform RN wrapper |
| Platform | React Native | 0.74.5 | UI framework |
| Platform | React | 18.2 | component model |
| Nav | @react-navigation/native | ^6.1 | navigation core |
| Nav | @react-navigation/bottom-tabs | ^6.6 | tab navigator |
| Nav | react-native-safe-area-context | 4.10.5 | safe insets |
| Nav | react-native-screens | 3.31.1 | native containers |
| State | Zustand | ^4.5 | store |
| State | AsyncStorage | 1.23.1 | event-log persistence |
| Validation | Zod | ^3.23 | runtime schema check |
| Render | react-native-svg | 15.2 | SVG primitives |
| Render | react-native-webview | 13.8.6 | KaTeX host |
| Render | KaTeX | 0.16.9 (CDN) | LaTeX → HTML |
| Pipeline | Python | 3.12 | content pipeline |
| Pipeline | NetworkX | ≥ 3.2 | DAG algorithms |
| Pipeline | pgmpy | ≥ 0.1.25 | PGM reference |
| Pipeline | spaCy | ≥ 3.7 | NLP |
| Pipeline | scikit-learn | ≥ 1.4 | TF-IDF / clustering |
| Pipeline | requests / bs4 / lxml | current | scraping |
| Pipeline | Kùzu | ≥ 0.6 | embedded graph DB |
| Pipeline | matplotlib | ≥ 3.8 | 3D viz |
| Pipeline | pyvis | ≥ 0.3 | HTML viz |

---

## 9. What is *not* used (and why it might look like it should be)

For reviewers who might expect these:

- **Redux / RTK** — Zustand suffices; see §4.
- **TanStack Query / SWR** — No server; no cache to invalidate.
- **Reanimated / Moti** — No custom animations beyond RN's built-ins.
- **NativeWind / styled-components** — Stock `StyleSheet.create` is
  enough for four screens; nothing to theme across.
- **MathJax** — KaTeX is faster and covers precalculus completely.
- **SQLite** — AsyncStorage is sufficient for a demo-sized log; the
  swap is one file when it matters.
- **Firebase / Supabase** — No backend yet; when we add one, it's a
  FastAPI service that already has its Python companions above.
- **Fastlane / EAS Build** — We don't ship binaries for the demo; Expo
  Go handles distribution.

---

## 10. Dependency footprint (rough)

- `node_modules` after `npm install`: ~450 MB (normal for RN).
- Production JS bundle: ~3–5 MB (Hermes-minified).
- Bundled JSON assets: ~180 KB total.
- Python venv for the pipeline: ~1.8 GB (spaCy model + scikit-learn
  dominate). Not shipped.

---

## 11. One-line role summary for every runtime dep

```
expo                           — cross-platform app shell & dev loop
react-native                   — native UI via React
react                          — component model
expo-status-bar                — OS status bar styling
@react-navigation/native       — navigation core
@react-navigation/bottom-tabs  — the four-tab shell
react-native-safe-area-context — device insets
react-native-screens           — native nav containers
zustand                        — tiny store for studentId + derived state
@react-native-async-storage/async-storage — event-log persistence
zod                            — validate LLM-authored questions
react-native-svg               — Tree & Cave layouts
react-native-webview           — hosts KaTeX for LaTeX math
KaTeX (CDN)                    — render LaTeX inside the WebView
```

That's the whole moving parts inventory.
