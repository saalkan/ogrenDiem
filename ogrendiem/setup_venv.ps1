# setup_venv.ps1 — recreate the exact Python venv used in the original project.
#
# Usage (from this folder):
#   .\setup_venv.ps1
#
# Requires Python 3.12 on PATH (the original venv was built with Python 3.12.10).
# If you have multiple Pythons, call explicitly:
#   py -3.12 -m venv .venv
# then re-run this script (it will detect the existing .venv and skip creation).

$ErrorActionPreference = "Stop"

$pythonCmd = "python"
$required  = "3.12"

Write-Host "[1/5] Checking Python version..." -ForegroundColor Cyan
$ver = & $pythonCmd --version 2>&1
if ($ver -notmatch "Python $required") {
    Write-Warning "Expected Python $required.x; got: $ver"
    Write-Warning "Continuing anyway, but pgmpy/spacy wheels may not match."
}

if (-not (Test-Path ".venv")) {
    Write-Host "[2/5] Creating .venv with $pythonCmd..." -ForegroundColor Cyan
    & $pythonCmd -m venv .venv
} else {
    Write-Host "[2/5] .venv already exists — reusing." -ForegroundColor Yellow
}

$venvPy = ".\.venv\Scripts\python.exe"

Write-Host "[3/5] Upgrading pip/setuptools/wheel..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip setuptools wheel

Write-Host "[4/5] Installing pinned dependencies from requirements.lock.txt..." -ForegroundColor Cyan
& $venvPy -m pip install -r requirements.lock.txt

Write-Host "[5/5] Done." -ForegroundColor Green
Write-Host ""
Write-Host "Activate with:" -ForegroundColor Cyan
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "or run commands directly via:"
Write-Host "    .\.venv\Scripts\python.exe -m graph.export_mobile"
