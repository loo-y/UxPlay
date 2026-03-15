[CmdletBinding()]
param(
    [string]$ProcessName = "uxplay",
    [int]$StartupWaitSeconds = 30,
    [int]$PollIntervalMs = 500
)

Add-Type @"
using System;
using System.Runtime.InteropServices;

public static class TopmostWindow {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(
        IntPtr hWnd,
        IntPtr hWndInsertAfter,
        int X,
        int Y,
        int cx,
        int cy,
        uint uFlags);

    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    public const UInt32 SWP_NOSIZE = 0x0001;
    public const UInt32 SWP_NOMOVE = 0x0002;
    public const UInt32 SWP_NOACTIVATE = 0x0010;
    public const UInt32 SWP_SHOWWINDOW = 0x0040;
}
"@

$deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
$seenWindow = $false

while ($true) {
    $processes = @(Get-Process -Name $ProcessName -ErrorAction SilentlyContinue)
    if ($processes.Count -eq 0) {
        if ($seenWindow -or (Get-Date) -ge $deadline) {
            break
        }
        Start-Sleep -Milliseconds $PollIntervalMs
        continue
    }

    $hasWindow = $false
    foreach ($process in $processes) {
        try {
            $null = $process.Refresh()
            $hwnd = $process.MainWindowHandle
            if ($hwnd -eq 0) {
                continue
            }
            $hasWindow = $true
            $seenWindow = $true
            [TopmostWindow]::SetWindowPos(
                [IntPtr]$hwnd,
                [TopmostWindow]::HWND_TOPMOST,
                0,
                0,
                0,
                0,
                [TopmostWindow]::SWP_NOMOVE -bor
                [TopmostWindow]::SWP_NOSIZE -bor
                [TopmostWindow]::SWP_NOACTIVATE -bor
                [TopmostWindow]::SWP_SHOWWINDOW
            ) | Out-Null
        } catch {
        }
    }

    if (-not $hasWindow -and (Get-Date) -ge $deadline -and -not $seenWindow) {
        break
    }

    Start-Sleep -Milliseconds $PollIntervalMs
}
