#!/usr/bin/env bash
# setup_venv.sh — recreate the exact Python venv used in the original project.
#
# Usage (from this folder):
#   bash setup_venv.sh
#
# Requires Python 3.12 on PATH (original venv was Python 3.12.10).
# If "python3" is a different version, set PYTHON=/path/to/python3.12.

set -euo pipefail

PYTHON="${PYTHON:-python3}"
REQUIRED="3.12"

echo "[1/5] Checking Python version..."
VER="$("$PYTHON" --version 2>&1 || true)"
if [[ "$VER" != *"Python $REQUIRED"* ]]; then
    echo "WARNING: expected Python $REQUIRED.x; got: $VER"
    echo "         Continuing anyway, but pgmpy/spacy wheels may not match."
fi

if [[ ! -d ".venv" ]]; then
    echo "[2/5] Creating .venv with $PYTHON..."
    "$PYTHON" -m venv .venv
else
    echo "[2/5] .venv already exists — reusing."
fi

VENV_PY=".venv/bin/python"

echo "[3/5] Upgrading pip/setuptools/wheel..."
"$VENV_PY" -m pip install --upgrade pip setuptools wheel

echo "[4/5] Installing pinned dependencies from requirements.lock.txt..."
"$VENV_PY" -m pip install -r requirements.lock.txt

echo "[5/5] Done."
echo
echo "Activate with:"
echo "    source .venv/bin/activate"
echo "or run commands directly via:"
echo "    .venv/bin/python -m graph.export_mobile"
