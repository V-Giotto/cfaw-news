param(
    [string]$Python = '',
    [int]$Port = 8000,
    [switch]$SkipInstall,
    [switch]$Reload
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVenvPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
Push-Location $taskRoot
try {
    if (-not (Test-Path -LiteralPath $taskVenvPython)) {
        $taskParentPython = Join-Path (Split-Path -Parent $taskRoot) '.venv\Scripts\python.exe'
        $taskCandidates = @($Python, $taskParentPython, 'python', 'py')
        $taskSelectedPython = $null
        foreach ($taskCandidate in $taskCandidates) {
            if (-not $taskCandidate) { continue }
            try {
                & $taskCandidate -c 'import sys; assert sys.version_info >= (3,11)' 2>$null
                if ($LASTEXITCODE -eq 0) { $taskSelectedPython = $taskCandidate; break }
            } catch { continue }
        }
        if (-not $taskSelectedPython) { throw 'Python 3.11+ was not found. Use -Python with a real interpreter path.' }
        & $taskSelectedPython -m venv '.venv'
        if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    }
    if (-not $SkipInstall) {
        & $taskVenvPython -m pip install -r requirements.lock
        if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
        & $taskVenvPython -m pip install --no-deps -e .
        if ($LASTEXITCODE -ne 0) { throw 'Python package installation failed.' }
        $taskNpm = (Get-Command npm.cmd -ErrorAction Stop).Source
        Push-Location frontend
        try {
            & $taskNpm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed. Node.js 22.12+ or 24 is required.' }
            & $taskNpm run build
            if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
        } finally { Pop-Location }
    }
    if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Frontend build is missing. Run without -SkipInstall.' }
    Write-Host "CFAW News: http://127.0.0.1:$Port  (Ctrl+C to stop)"
    $taskArguments = @('-m', 'uvicorn', 'cfaw_news.main:create_app', '--factory', '--host', '127.0.0.1', '--port', "$Port")
    if ($Reload) { $taskArguments += @('--reload', '--reload-dir', 'backend') }
    & $taskVenvPython @taskArguments
    if ($LASTEXITCODE -ne 0) { throw 'Server failed to start. Check the port and the error above.' }
} finally { Pop-Location }
