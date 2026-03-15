# Windows iPhone Mirroring

This repository already contains the AirPlay receiver implementation. On Windows, the practical setup work is:

1. build `uxplay.exe`
2. make service discovery available with Bonjour or the bundled BLE beacon
3. start UxPlay with Windows-friendly sinks

The helper script [`scripts/start-iphone-mirroring.ps1`](../scripts/start-iphone-mirroring.ps1) automates that startup path.

For this specific machine, the validated working state is documented in [`docs/windows-successful-mirroring-state.md`](./windows-successful-mirroring-state.md).

The default one-click Windows launcher enables an always-on-top video window, so the mirrored content stays above other desktop windows.
The desktop host launcher uses its own application window instead of the standalone `Direct3D12 Renderer` window, so toggling topmost applies to the host window itself.

For day-to-day use on this machine, prefer the one-click wrapper in the repository root:

```cmd
launch-uxplay-windows.cmd
```

If you want the same launch path without forced topmost behavior, use:

```cmd
launch-uxplay-windows-no-topmost.cmd
```

If you want a small settings window in front of the existing console-based launch flow, use:

```cmd
launch-uxplay-windows-gui.cmd
```

If you want the mirrored video embedded inside a dedicated desktop application window, use:

```cmd
launch-uxplay-desktop-app.cmd
```

This desktop app is implemented with `PySide6` and uses the working Direct3D renderer path as the video surface source, while the host window itself owns the settings bar and topmost toggle.

If you want to use the PowerShell wrapper instead, run it from PowerShell rather than Explorer double-click:

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-uxplay-windows.ps1
```

## Prerequisites

- Build `uxplay.exe` from this repository, or install it to `C:\msys64\ucrt64\bin\uxplay.exe`.
- Install the GStreamer plugins described in the README.
- Allow `uxplay.exe` through Windows Firewall.
- For BLE discovery, install Python 3 plus the dependencies described in `README.md`:
  - `psutil`
  - `PyGObject`
  - `winrt-Windows.Foundation`
  - `winrt-Windows.Foundation.Collections`
  - `winrt-Windows.Devices.Bluetooth.Advertisement`
  - `winrt-Windows.Storage.Streams`

## Start Mirroring

From the repository root in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-iphone-mirroring.ps1
```

The script will:

- prefer Bonjour service discovery if the `Bonjour Service` Windows service is already running
- otherwise start the bundled Bluetooth LE beacon and pass `-ble` to `uxplay.exe`
- use `d3d12videosink` and `wasapisink` by default, which match the README's Windows guidance

The GUI launcher stores its settings in `runtime\windows-mirroring\launcher-settings.json`.

Useful options:

```powershell
.\scripts\start-iphone-mirroring.ps1 -ServerName "My PC"
.\scripts\start-iphone-mirroring.ps1 -UseBleBeacon
.\scripts\start-iphone-mirroring.ps1 -SkipBleBeacon
.\scripts\start-iphone-mirroring.ps1 -UxPlayPath .\build\uxplay.exe
.\scripts\start-iphone-mirroring.ps1 -Ipv4Address 192.168.1.20
```

After it starts, use `Control Center > Screen Mirroring` on the iPhone and pick the server name shown by the script.

## Notes

- `-UseBleBeacon` is the safer choice when Bonjour is not installed on Windows.
- If iPhone discovery still fails, confirm that the PC and iPhone are on the same LAN and that Windows Firewall is not blocking `uxplay.exe`.
- BLE discovery requires a working Bluetooth adapter on the Windows machine.
