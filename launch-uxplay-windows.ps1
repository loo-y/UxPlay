$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Start-Process -FilePath "cmd.exe" -WorkingDirectory $PSScriptRoot -ArgumentList @("/k", ".\\scripts\\run-uxplay-windows.cmd")
