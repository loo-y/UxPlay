@echo off
setlocal

set REPO=C:\Users\luyi1\code\github\UxPlay
set TOPMOST_ARGS=-top
set SERVER_NAME=UxPlay-Windows
set PATH=%REPO%\.local\msys64\ucrt64\bin;%REPO%\.local\msys64\usr\bin;%PATH%
set GST_PLUGIN_SCANNER=%REPO%\.local\msys64\ucrt64\libexec\gstreamer-1.0\gst-plugin-scanner.exe
set GST_PLUGIN_SYSTEM_PATH_1_0=%REPO%\.local\msys64\ucrt64\lib\gstreamer-1.0
set GST_REGISTRY_FORK=no

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--no-topmost" (
  set "TOPMOST_ARGS="
  shift
  goto parse_args
)
if /I "%~1"=="--name" (
  if not "%~2"=="" (
    set "SERVER_NAME=%~2"
    shift
  )
  shift
  goto parse_args
)
shift
goto parse_args

:args_done

cd /d %REPO%
if not exist runtime\windows-mirroring mkdir runtime\windows-mirroring
set GST_REGISTRY=%REPO%\runtime\windows-mirroring\gstreamer-registry.bin
del /q "%GST_REGISTRY%" 2>nul

echo Starting UxPlay-Windows...
echo.

gst-inspect-1.0 app libav playback autodetect videoparsersbad >nul 2>&1
if defined TOPMOST_ARGS (
  start "" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO%\scripts\keep-uxplay-topmost.ps1"
)
.\build-manual\uxplay.exe -n "%SERVER_NAME%" -nh %TOPMOST_ARGS% -vs d3d12videosink -as wasapisink

echo.
echo uxplay exited with code %ERRORLEVEL%
echo.
pause
