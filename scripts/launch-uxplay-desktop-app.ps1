$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\pythonw.exe"),
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    "C:\Users\luyi1\code\github\livesoul-agent\.venv\Scripts\pythonw.exe",
    "C:\Users\luyi1\code\github\livesoul-agent\.venv\Scripts\python.exe"
)

$pythonExe = $pythonCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $pythonExe) {
    throw "No suitable Python runtime found. Expected a local .venv or livesoul-agent\\.venv with PySide6 installed."
}

$appScript = Join-Path $repoRoot "scripts\uxplay_desktop_qt.py"
Start-Process -FilePath $pythonExe -WorkingDirectory $repoRoot -ArgumentList @($appScript)
