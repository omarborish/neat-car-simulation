$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
try {
    $pythonPath = Find-SimulationPython
    if (-not $pythonPath) {
        throw 'Install Python 3.10 to 3.13 (with pip), then run Setup.bat again.'
    }
    $venvPath = Join-Path $projectRoot '.venv'
    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host 'Creating a Python environment for this project...'
        & $pythonPath -m venv $venvPath
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
    }
    Write-Host 'Installing the two required libraries...'
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $projectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installation failed. Check your internet connection and try Setup.bat again.' }
    Write-Host 'Setup complete. Double-click Launch.bat to start.' -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
