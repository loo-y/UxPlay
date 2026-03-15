# Windows Successful Mirroring State

This is the known-good launch path that successfully mirrored an iPhone to this Windows machine during local validation.

## Required environment

- Portable MSYS2 runtime under `.local\msys64`
- Built executable at `build-manual\uxplay.exe`
- Installed MSYS2 package:
  - `mingw-w64-ucrt-x86_64-json-glib`

## Required GStreamer environment

- `GST_REGISTRY_FORK=no`
- `GST_PLUGIN_SCANNER=%REPO%\.local\msys64\ucrt64\libexec\gstreamer-1.0\gst-plugin-scanner.exe`
- `GST_PLUGIN_SYSTEM_PATH_1_0=%REPO%\.local\msys64\ucrt64\lib\gstreamer-1.0`
- `GST_REGISTRY=%REPO%\runtime\windows-mirroring\gstreamer-registry.bin`

Before launching `uxplay.exe`, rebuild or warm the local registry with:

```cmd
gst-inspect-1.0 app libav playback autodetect videoparsersbad >nul 2>&1
```

## Required UxPlay arguments

```cmd
.\build-manual\uxplay.exe -n UxPlay-Windows -nh -top -vs d3d12videosink -as wasapisink
```

`-top` is the Windows-only always-on-top flag used for the local mirroring window.

## Required launch method

Do not launch through the transient sandbox-owned console pattern that closes when the parent session exits.

Use a standalone desktop `cmd` window outside the sandbox:

```powershell
Start-Process -FilePath 'cmd.exe' -WorkingDirectory $repo -ArgumentList @('/k','.\\scripts\\run-uxplay-windows.cmd')
```

Observed behavior during debugging:

- Unstable launch pattern:
  transient child consoles started from the restricted interactive tool session could disappear when the parent session ended
- Stable launch pattern:
  a standalone desktop `cmd.exe` process running `scripts\run-uxplay-windows.cmd`
- Recommended daily-use entrypoint:
  double-click `launch-uxplay-windows.cmd`
- Settings entrypoint:
  double-click `launch-uxplay-windows-gui.cmd`
- Embedded desktop app entrypoint:
  double-click `launch-uxplay-desktop-app.cmd`

## Known-good entrypoint

Use:

```cmd
scripts\run-uxplay-windows.cmd
```

This script sets the environment, rebuilds the local GStreamer registry, and starts `uxplay.exe` in the known-good configuration.

For one-click local use from the repository root, use either:

```cmd
launch-uxplay-windows.cmd
```

or, if you do not want the mirror window pinned above everything:

```cmd
launch-uxplay-windows-no-topmost.cmd
```

or, if you want a small launcher window with saved settings:

```cmd
launch-uxplay-windows-gui.cmd
```

or, if you want the mirrored video embedded inside a dedicated desktop application window:

```cmd
launch-uxplay-desktop-app.cmd
```

The current desktop app implementation uses `PySide6` as the host UI layer.

or

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-uxplay-windows.ps1
```

Both wrappers launch the same known-good `scripts\run-uxplay-windows.cmd` flow in a standalone desktop console window.

Note on `.ps1`:

- Do not rely on double-clicking `launch-uxplay-windows.ps1` in Explorer, because some Windows setups will prompt for an app association instead of executing it.
- If you want to use the PowerShell wrapper, launch it from an existing PowerShell terminal:

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-uxplay-windows.ps1
```

- For normal use, prefer double-clicking `launch-uxplay-windows.cmd`.
