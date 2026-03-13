@echo off
setlocal

set REPO=C:\Users\luyi1\code\github\UxPlay
set PATH=%REPO%\.local\msys64\ucrt64\bin;%REPO%\.local\msys64\usr\bin;%PATH%
set GST_PLUGIN_SCANNER=%REPO%\.local\msys64\ucrt64\libexec\gstreamer-1.0\gst-plugin-scanner.exe
set GST_PLUGIN_SYSTEM_PATH_1_0=%REPO%\.local\msys64\ucrt64\lib\gstreamer-1.0
set GST_REGISTRY_FORK=no

cd /d %REPO%
if not exist runtime\windows-mirroring mkdir runtime\windows-mirroring
set GST_REGISTRY=%REPO%\runtime\windows-mirroring\gstreamer-registry.bin
del /q "%GST_REGISTRY%" 2>nul

echo Starting UxPlay-Windows...
echo.

gst-inspect-1.0 app libav playback autodetect videoparsersbad >nul 2>&1
.\build-manual\uxplay.exe -n UxPlay-Windows -nh -vs d3d12videosink -as wasapisink

echo.
echo uxplay exited with code %ERRORLEVEL%
echo.
pause
