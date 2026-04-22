# setup_uv.ps1 — one-shot setup using `uv` (fast-path, no pre-installed Python needed).
#
# Usage (from this folder):
#   .\setup_uv.ps1
#
# `uv` downloads Python 3.12 for you (via python-build-standalone), creates
# a venv, and installs the locked dependencies — all in ~20 seconds.
#
# Install uv first (one-liner):
#   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Checking for uv..." -ForegroundColor Cyan
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "uv is not installed." -ForegroundColor Red
    Write-Host "Install it with:" -ForegroundColor Yellow
    Write-Host '    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host "then re-run this script."
    exit 1
}
Write-Host "uv found: $(uv --version)" -ForegroundColor Green

Write-Host "[2/4] Ensuring Python 3.12 is available (uv will download if needed)..." -ForegroundColor Cyan
uv python install 3.12

Write-Host "[3/4] Creating .venv pinned to Python 3.12..." -ForegroundColor Cyan
uv venv --python 3.12 .venv

Write-Host "[4/4] Installing pinned dependencies from requirements.lock.txt..." -ForegroundColor Cyan
uv pip install --python .\.venv\Scripts\python.exe -r requirements.lock.txt

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Activate with:" -ForegroundColor Cyan
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "or run commands directly via:"
Write-Host "    .\.venv\Scripts\python.exe -m graph.export_mobile"
