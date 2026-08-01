# Bootstrap a local Python 3.14 dev environment (Windows).
# Does NOT modify the global interpreter or global site-packages.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

Write-Host "== Verifying Python 3.14 ==" -ForegroundColor Cyan
py -3.14 --version
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 3.14 not found. Install it: winget install --id Python.Python.3.14 --scope user"
    exit 1
}

Write-Host "== Creating local .venv ==" -ForegroundColor Cyan
py -3.14 -m venv .venv

$py = ".\.venv\Scripts\python.exe"
Write-Host "== Upgrading packaging tools ==" -ForegroundColor Cyan
& $py -m pip install --upgrade pip setuptools wheel

Write-Host "== Installing core + dev (pinned constraints) ==" -ForegroundColor Cyan
& $py -m pip install -e ".[dev]" -c requirements/constraints-python314.txt

Write-Host "== pip check ==" -ForegroundColor Cyan
& $py -m pip check

Write-Host "== Versions ==" -ForegroundColor Cyan
& $py --version
& $py -m pip --version
& $py -c "import numpy, pandas, sklearn; print('numpy', numpy.__version__, 'pandas', pandas.__version__, 'sklearn', sklearn.__version__)"
Write-Host "Bootstrap complete. Activate with: .\.venv\Scripts\Activate.ps1" -ForegroundColor Green
