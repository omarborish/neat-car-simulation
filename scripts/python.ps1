function Find-SimulationPython {
    param([switch]$RequireDependencies)
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $candidates = @(
        (Join-Path $projectRoot '.venv\Scripts\python.exe'),
        (Join-Path $env:USERPROFILE 'anaconda3\python.exe'),
        (Join-Path $env:USERPROFILE 'miniconda3\python.exe')
    )
    foreach ($version in @('313', '312', '311', '310')) {
        $candidates += Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe"
    }
    $commands = Get-Command python -All -ErrorAction SilentlyContinue
    foreach ($command in $commands) {
        if ($command.Source -and $command.Source -notlike '*\WindowsApps\*') {
            $candidates += $command.Source
        }
    }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        $installed = & $launcher.Source -0p 2>$null
        foreach ($line in $installed) {
            if ($line -match '([A-Za-z]:\\.*python\.exe)') {
                $candidates += $Matches[1]
            }
        }
    }
    $probe = 'import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)'
    if ($RequireDependencies) {
        $probe = "import sys, importlib.metadata as m; import pygame, neat; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) and m.version('pygame')=='2.6.1' and m.version('neat-python')=='0.92' else 1)"
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            # Suppress version probes; only return the chosen path.
            try {
                & $candidate -B -c $probe *> $null
                if ($LASTEXITCODE -eq 0) { return $candidate }
            } catch { continue }
        }
    }
    return $null
}
