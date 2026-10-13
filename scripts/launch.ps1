param([switch]$CheckOnly, [switch]$NoBrowser, [ValidateRange(0, 65535)][int]$Port = 8765,
      [ValidateRange(1, 120)][int]$StartupTimeoutSeconds = 35)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python.ps1')
$projectRoot = (Get-Item -LiteralPath (Split-Path -Parent $PSScriptRoot)).FullName
try {
    $pythonPath = Find-SimulationPython -RequireDependencies
    if (-not $pythonPath) {
        throw 'The required Python libraries are missing. Double-click Setup.bat first. Use Python 3.10 to 3.13.'
    }
    if ($CheckOnly) {
        Write-Output $pythonPath
        exit 0
    }
    $logFolder = Join-Path $projectRoot 'logs'
    New-Item -ItemType Directory -Force -Path $logFolder | Out-Null
    $env:PYGAME_HIDE_SUPPORT_PROMPT = '1'
    # The server owns canonicalization and the per-checkout identity filename.
    Push-Location -LiteralPath $projectRoot
    try {
        $launchIdentity = & $pythonPath -B -c "import json; from server import default_identity_file, project_identity; print(json.dumps(project_identity() | {'identity_file': str(default_identity_file())}))"
        if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the local server identity.' }
        $launchIdentity = $launchIdentity | ConvertFrom-Json
        $identityFile = $launchIdentity.identity_file
        $expectedProjectRoot = $launchIdentity.project_root
    } finally { Pop-Location }
    $launchId = [Guid]::NewGuid().ToString('N')
    $outputLog = Join-Path $logFolder "launch-$launchId.log"
    $errorLog = Join-Path $logFolder "launch-error-$launchId.log"
    $serverPath = Join-Path $projectRoot 'server.py'
    $arguments = @('-B', ('"' + $serverPath + '"'), '--no-browser', '--port', $Port.ToString(),
                   '--identity-file', ('"' + $identityFile + '"'))
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $outputLog -RedirectStandardError $errorLog -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $readyUrl = $null
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            if (Test-Path -LiteralPath $identityFile -PathType Leaf) {
                $record = Get-Content -LiteralPath $identityFile -Raw | ConvertFrom-Json
                $url = [Uri]$record.url
                if ($record.application_id -eq 'neat-car-simulation' -and $record.protocol -eq 1 -and
                    $record.project_root -eq $expectedProjectRoot -and $url.Scheme -eq 'http' -and
                    $url.Host -eq '127.0.0.1' -and $url.Port -gt 0 -and $url.AbsolutePath -eq '/' -and
                    -not $url.UserInfo -and -not $url.Query -and -not $url.Fragment) {
                    $identity = Invoke-RestMethod -Uri ($url.AbsoluteUri + 'api/identity') -TimeoutSec 1 -MaximumRedirection 0
                    if ($identity.application_id -eq 'neat-car-simulation' -and $identity.protocol -eq 1 -and
                        $identity.project_root -eq $expectedProjectRoot) {
                        $state = Invoke-RestMethod -Uri ($url.AbsoluteUri + 'api/state') -TimeoutSec 1 -MaximumRedirection 0
                        if ($state.schema_version -eq 1) { $readyUrl = $url.AbsoluteUri; break }
                    }
                }
            }
        } catch { # A listener may be binding or the worker may still be starting.
        }
        $process.Refresh()
        if ($process.HasExited -and $process.ExitCode -ne 0) { break }
        Start-Sleep -Milliseconds 100
    }
    if (-not $readyUrl) {
        $process.Refresh()
        if (-not $process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
        throw "The browser simulation could not become ready. Check $errorLog and $outputLog. Run Setup.bat if a library is missing."
    }
    if (-not $NoBrowser) { Start-Process $readyUrl }
    Write-Output "Simulation ready: $readyUrl"
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $CheckOnly -and -not $NoBrowser) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'NEAT Car Simulation') | Out-Null
    }
    exit 1
}
