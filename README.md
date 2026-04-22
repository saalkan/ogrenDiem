# öğrenDiem: Portable Export

This directory is a clean copy of the full `ogrenDiem` project
without any generated or installed artifacts. To turn it back into a
working development environment you only need two installers and a
few minutes.

## What was excluded

The following were **not** copied from the original workspace:

- `ogrendiem/.venv/` the Python virtual environment
  (regenerated from `requirements.lock.txt`; see below)
- `ogrendiem-app/node_modules/` npm dependencies
  (regenerated with `npm install`)
- `ogrendiem-app/.expo/` Expo's local cache (regenerated on first run)
- `**/__pycache__/`, `**/*.pyc`, `**/*.pyo` — Python bytecode caches
- `**/bin/`, `**/obj/`, `**/dist/`, `**/build/`, `**/.next/`,
  `**/.turbo/` any build output directories
- `.git/` version control history (not part of the deliverable)
- `toplumsal-katki.rar` redundant archive of the source itself

Everything else (source code, bundled JSON assets, documentation,
LaTeX reports, PDFs, scripts, the `precalc_db` graph database) is
included verbatim.

## What was added

- `ogrendiem/requirements.lock.txt` a full `pip freeze` of the
  original venv (93 packages, exact versions incl. the spaCy model URL).
- `ogrendiem/setup_uv.ps1` / `setup_uv.sh` **fast-path** setup via
  `uv` (downloads Python 3.12 on demand; no pre-installed Python needed).
- `ogrendiem/setup_venv.ps1` / `setup_venv.sh` classic `venv` setup
  (requires Python 3.12 pre-installed).
- `README_EXPORT.md` this file.

## How to restore the Python venv

Two paths, pick one:

### Path A: `uv` (recommended, no Python required upfront)

[`uv`](https://github.com/astral-sh/uv) is a fast Python-package manager
that can **download Python itself** for you. If you use it, you don't
need Python 3.12 pre-installed. `uv` will fetch a self-contained
Python 3.12 build (via `python-build-standalone`).

Install `uv` (one line, no admin needed):

```powershell
# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```
```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then run the setup:

```powershell
cd ogrendiem
.\setup_uv.ps1        # Windows
```
```bash
cd ogrendiem
bash setup_uv.sh      # macOS / Linux
```

Total time: ~20 seconds to a minute.

### Path B: standard `venv` (requires Python 3.12 pre-installed)

Use this if you already have Python 3.12 installed and prefer not to
add another tool. The original venv was Python 3.12.10; any 3.12.x is
fine. 3.11 or 3.13 *may* work but the lockfile wheels were resolved
for 3.12 and source builds are likely.

**Windows (PowerShell):**
```powershell
cd ogrendiem
.\setup_venv.ps1
```

If PowerShell blocks the script, run once per shell:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**macOS / Linux (bash / zsh):**
```bash
cd ogrendiem
bash setup_venv.sh
```

If your default `python3` isn't 3.12:
```bash
PYTHON=/usr/local/bin/python3.12 bash setup_venv.sh
```

Either `setup_venv.*` script performs five steps:

1. Verify the Python version.
2. Create `ogrendiem/.venv` (skipped if it already exists).
3. Upgrade `pip`, `setuptools`, `wheel` inside the venv.
4. `pip install -r requirements.lock.txt` installs **every** package
   at the exact version the original project used, including the
   `en_core_web_sm` spaCy model (pulled from its GitHub release URL).
5. Print activation instructions.

Installation takes 3–8 minutes depending on network and CPU
(the heaviest wheels are `scikit-learn`, `scipy`, `spacy`, `pgmpy`).

### Why not bundle Python itself in the repo?

A `venv` is a thin redirection layer on top of a base Python install,
not a self-contained Python. Shipping `.venv/` would break on any
machine whose base interpreter lives at a different path. Path A (`uv`)
is the closest thing to "Python bundled with the project". The
download happens on the user's machine but it's fully automatic.

## How to restore the React Native app

```bash
cd ogrendiem-app
npm install
npm start
```

See `ogrendiem-app/DEMO_GUIDE.md` for the full "scan the QR with Expo
Go" flow.

## Two files, two lock mechanisms

- **`ogrendiem/requirements.txt`** (original) loose minimum-version
  constraints. Good for *upgrading* to latest compatible versions.
- **`ogrendiem/requirements.lock.txt`** (added here) exact pins of
  every transitive dependency as they existed in the original venv.
  Good for *reproducing* the exact environment the app was tested in.

The setup scripts use the lock file. If you want a fresh resolve:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Layout reminder

```
ogrenDiem/
├── READM.md                 ← you are here
├── ogrendiem/                        Python content pipeline
│   ├── setup_uv.ps1     setup_uv.sh      (fast path, uses uv)
│   ├── setup_venv.ps1   setup_venv.sh    (classic path, uses venv)
│   ├── requirements.txt             (loose)
│   ├── requirements.lock.txt        (pinned)
│   ├── graph/  nlp/  pgm/  scraper/  tutor/  lib/  data/
│   ├── precalc_db                   (Kùzu graph DB, single file)
│   └── README.md
├── ogrendiem-app/                    React Native + Expo app
│   ├── DEMO_GUIDE.md
│   ├── ARCHITECTURE.md
│   ├── TECH_STACK.md
│   ├── package.json                 (run `npm install`)
│   ├── App.tsx  app.json  babel.config.js  tsconfig.json
│   ├── src/
│   └── assets/
```

## Check after restore

From inside the restored Python venv:

```bash
python -c "import pgmpy, networkx, spacy; print(pgmpy.__version__, networkx.__version__, spacy.__version__)"
# expected: 1.1.0 3.6.1 3.8.14
```

From inside the app folder after `npm install`:

```bash
npm run typecheck
```

Both should run without error. At that point the project is in the
same shape it was in on the day the export was produced.
