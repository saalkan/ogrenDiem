#!/usr/bin/env bash
# setup_uv.sh — one-shot setup using `uv` (fast-path, no pre-installed Python needed).
#
# Usage (from this folder):
#   bash setup_uv.sh
#
# `uv` downloads Python 3.12 for you (via python-build-standalone), creates
# a venv, and installs the locked dependencies — all in ~20 seconds.
#
# Install uv first (one-liner):
#   curl -LsSf https://astral.sh/uv/install.sh | sh

set -euo pipefail

echo "[1/4] Checking for uv..."
if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv is not installed." >&2
    echo "Install it with:" >&2
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
    echo "then re-run this script." >&2
    exit 1
fi
echo "uv found: $(uv --version)"

echo "[2/4] Ensuring Python 3.12 is available (uv will download if needed)..."
uv python install 3.12

echo "[3/4] Creating .venv pinned to Python 3.12..."
uv venv --python 3.12 .venv

echo "[4/4] Installing pinned dependencies from requirements.lock.txt..."
uv pip install --python ./.venv/bin/python -r requirements.lock.txt

echo
echo "Done."
echo "Activate with:"
echo "    source .venv/bin/activate"
echo "or run commands directly via:"
echo "    .venv/bin/python -m graph.export_mobile"
