param([switch]$CheckOnly, [int]$Frames = 0)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
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
    $appPath = Join-Path $projectRoot 'app.py'
    $arguments = @('-B', ('"' + $appPath + '"'))
    if ($Frames -gt 0) { $arguments += @('--frames', $Frames.ToString()) }
    $process = Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logFolder 'launch.log') -RedirectStandardError (Join-Path $logFolder 'launch-error.log') -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "The simulation stopped with an error. Details are in $logFolder."
    }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    if (-not $CheckOnly -and $Frames -eq 0) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'NEAT Car Simulation') | Out-Null
    }
    exit 1
}
