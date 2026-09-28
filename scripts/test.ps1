# Run the full offline test + static-analysis suite (Windows).
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = ".\.venv314\Scripts\python.exe" }
if (-not (Test-Path $py)) { Write-Error "No local venv. Run scripts\bootstrap.ps1 first."; exit 1 }

$fail = 0
function Run($name, $cmd) {
    Write-Host "== $name ==" -ForegroundColor Cyan
    & $cmd
    if ($LASTEXITCODE -ne 0) { Write-Host "$name FAILED" -ForegroundColor Red; $script:fail = 1 }
}

Run "pytest + coverage" { & $py -m pytest --cov --cov-report=term-missing }
Run "ruff check"        { & $py -m ruff check . }
Run "ruff format check" { & $py -m ruff format --check . }
Run "mypy"              { & $py -m mypy src }
Run "bandit"            { & $py -m bandit -r src -x src/guardrail_comparison.py,src/explore_hackaprompt.py -q }
Run "pip-audit"         { & $py -m pip_audit }

if ($fail -ne 0) { Write-Host "SUITE FAILED" -ForegroundColor Red; exit 1 }
Write-Host "ALL CHECKS PASSED" -ForegroundColor Green
