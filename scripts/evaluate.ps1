# Attempt to reproduce the ML held-out evaluation (Windows).
# NOTE: this is currently BLOCKED (audit C1/B1). The committed model artifact is
# marked trusted=false and, even when force-loaded, produces invalid predictions
# under a newer scikit-learn (see reports/final-results.md). Training data to
# regenerate a valid model is missing. This script fails with that explanation
# rather than silently emitting meaningless metrics.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = ".\.venv314\Scripts\python.exe" }

Write-Host "== Verifying artifact provenance ==" -ForegroundColor Cyan
& $py -c "import sys; sys.path.insert(0,'src'); import model_loader as m; [print(n, m.verify_artifact(m.MODELS_DIR / n)['trusted']) for n in ('classifier.pkl','vectorizer.pkl')]"

Write-Host ""
Write-Host "BLOCKED: model artifact is untrusted and not reproducible (audit C1/B1)." -ForegroundColor Yellow
Write-Host "To restore evaluation: provide datasets/prompt_injection_500.csv and" -ForegroundColor Yellow
Write-Host "datasets/benign_500.csv (with provenance per datasets/README.md), then run:" -ForegroundColor Yellow
Write-Host "  $py src\ml_detector.py train --dataset synthetic" -ForegroundColor Yellow
Write-Host "  $py src\ml_detector.py evaluate --dataset datasets\eval_dataset_v2.csv" -ForegroundColor Yellow
exit 2
