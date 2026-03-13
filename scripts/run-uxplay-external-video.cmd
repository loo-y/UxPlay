@echo off
setlocal

set REPO=C:\Users\luyi1\code\github\UxPlay
set PATH=%REPO%\.local\msys64\ucrt64\bin;%REPO%\.local\msys64\usr\bin;%PATH%
set GST_PLUGIN_SCANNER=%REPO%\.local\msys64\ucrt64\libexec\gstreamer-1.0\gst-plugin-scanner.exe
set GST_PLUGIN_SYSTEM_PATH_1_0=%REPO%\.local\msys64\ucrt64\lib\gstreamer-1.0

cd /d %REPO%
if not exist runtime\windows-mirroring mkdir runtime\windows-mirroring

echo Starting external video receiver on UDP 5000...
start "UxPlay Video Receiver" cmd /k gst-launch-1.0 -v udpsrc port=5000 ! "application/x-rtp, media=video, clock-rate=90000, encoding-name=H264, payload=96" ! rtph264depay ! h264parse ! decodebin ! videoconvert ! autovideosink sync=false

timeout /t 2 >nul

echo Starting UxPlay-Windows...
echo Log: runtime\windows-mirroring\external-uxplay.log
echo.

.\build-manual\uxplay.exe -n UxPlay-Windows -nh -a -vrtp "config-interval=1 ! udpsink host=127.0.0.1 port=5000" 1> runtime\windows-mirroring\external-uxplay.log 2>&1

echo.
echo uxplay exited with code %ERRORLEVEL%
echo.
type runtime\windows-mirroring\external-uxplay.log
echo.
pause
