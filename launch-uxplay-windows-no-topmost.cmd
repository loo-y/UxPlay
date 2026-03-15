@echo off
setlocal
cd /d "%~dp0"
call scripts\run-uxplay-windows.cmd --no-topmost
