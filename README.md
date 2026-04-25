## Prerequisites

- **Node.js 20.x or 22.x** on the laptop (`node -v` to check).
- **Expo Go** installed on the phone from the Play Store / App Store.
- **A USB cable** that does data, not just power.
- The phone and laptop near each other.

## One-time setup

Open a terminal in `ogrendiem-app/` and run:

```cmd
npm install
```

Three to five minutes. Installs the dependency tree from `package.json`.

If you ever see `Unable to resolve "<package>"` later, that package is
missing from `package.json`. Add it with:

```cmd
npx expo install <package>
```

(Use `npx expo install`, not `npm install` — it picks the version
matching the Expo SDK.)

## Connecting the phone: USB tethering (recommended)

Wi-Fi between phone and laptop works in theory but is fragile: routers
with client isolation, guest networks, VPNs, and Windows tagging
networks as "Public" all break it silently. USB tethering bypasses
all of that.

1. Plug phone into laptop via USB.
2. On the phone: **Settings → Network & Internet → Hotspot & tethering
   → USB tethering → ON**. (iPhone: enable Personal Hotspot, then
   plug in.)
3. Find that adapter's IPv4:

   ```cmd
   ipconfig
   ```

   Look for the entry with the tether adapter's name. The IP will be
   in `192.168.42.x`, `172.20.10.x`, or `10.x.x.x` depending on phone
   model and carrier. Note the laptop-side address — call it `LAPTOP_IP`.

5. **Tag the tether connection as Private** (Settings → Network &
   Internet → click the tether connection → Network profile → Private).
   This stops Windows Firewall from blocking inbound port 8081.

## Starting Metro

In cmd, in `ogrendiem-app/`:

```cmd
set REACT_NATIVE_PACKAGER_HOSTNAME=LAPTOP_IP
npx expo start --clear
```

Replace `LAPTOP_IP` with the actual address from `ipconfig` (no quotes,
no spaces around `=`). The `--clear` flag wipes Metro's transform cache; 
always use it on the first start of a session.

The env var is critical: a Windows laptop usually has 3+ network
interfaces (Wi-Fi, USB tether, and various virtual adapters). Expo
guesses one for the QR code and often picks the wrong one. The env var
tells it which IP to advertise.

## Sanity check before scanning

Open the phone's browser and visit `http://LAPTOP_IP:8081`. If you see
a Metro/Expo response, networking is good. If it times out, the
firewall is blocking; set the tether network to Private (step 5
above) or open the port:

```powershell
New-NetFirewallRule -DisplayName "Expo Metro 8081" -Direction Inbound `
  -Protocol TCP -LocalPort 8081 -Action Allow -Profile Any
```

(PowerShell as Administrator.)

## Loading the app

1. Open Expo Go on the phone.
2. Scan the QR code shown in the terminal (or in the browser tab Expo
   opens).
3. First load takes 30–90 seconds (Metro bundles ~700 modules).
4. App opens to the Garden tab. Pick an emoji to start.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Failed to download remote update` | Phone can't reach Metro | Check `REACT_NATIVE_PACKAGER_HOSTNAME` is the tether IP, not Wi-Fi. Browser-test `http://LAPTOP_IP:8081` from phone. |
| `Packager is not running at http://X.X.X.X:8081` | QR has wrong IP for current network | Same as above; set the env var to the right interface. |
| `Cannot find module 'babel-preset-expo'` | Half-installed `node_modules` | `rmdir /s /q node_modules` + `del /q package-lock.json` + `npm install` |
| `Unable to resolve "<package>"` from App.tsx | Package missing from `package.json` | `npx expo install <package>` |
| `Project is incompatible with this version of Expo Go` | SDK mismatch | The repo is on SDK 54. Upgrade Expo Go from the Play Store, or downgrade the project: `npx expo install expo@<your-version>` then `npx expo install --fix` |
| Bundling hangs at "X modules" forever | Stale Metro cache | Ctrl+C, restart with `npx expo start --clear` |
| Bundle starts then errors mid-way | Cancelled previous build left partial cache | Same — `--clear` |


# Would you like to edit the app?
## öğrenDiem: Portable Export

This directory is a clean copy of the full `ogrenDiem` project
without any generated or installed artifacts. To turn it back into a
working development environment you only need two installers and a
few minutes.

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
