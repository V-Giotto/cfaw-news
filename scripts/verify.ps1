$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
Push-Location $taskRoot
try {
    & $taskPython -m ruff check backend tests evals
    if ($LASTEXITCODE -ne 0) { throw 'Static checks failed' }
    & $taskPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
    & $taskPython evals/run_baseline.py
    if ($LASTEXITCODE -ne 0) { throw 'Seed evaluation failed' }
    Push-Location frontend
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
} finally { Pop-Location }
