[CmdletBinding()]
param(
    [string]$UxPlayPath,
    [string]$ServerName = "UxPlay",
    [string]$VideoSink = "d3d11videosink",
    [string]$AudioSink = "wasapisink",
    [string]$Ipv4Address,
    [string]$BleDataPath,
    [switch]$UseBleBeacon,
    [switch]$SkipBleBeacon
)

$ErrorActionPreference = "Stop"

function Resolve-UxPlayPath {
    param(
        [string]$ExplicitPath,
        [string]$RepoRoot
    )

    $candidates = @(
        $ExplicitPath,
        (Join-Path $RepoRoot "build\uxplay.exe"),
        (Join-Path $RepoRoot "build\src\uxplay.exe"),
        "C:\msys64\ucrt64\bin\uxplay.exe"
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    throw "uxplay.exe not found. Build the project first, or pass -UxPlayPath."
}

function Add-RuntimePath {
    param(
        [string]$RepoRoot,
        [string]$ExecutablePath
    )

    $runtimeCandidates = @(
        (Split-Path -Parent $ExecutablePath),
        (Join-Path $RepoRoot ".local\\msys64\\ucrt64\\bin"),
        (Join-Path $RepoRoot ".local\\msys64\\usr\\bin")
    ) | Where-Object { $_ -and (Test-Path $_) }

    $existing = @()
    if ($env:PATH) {
        $existing = $env:PATH.Split(';')
    }

    foreach ($candidate in $runtimeCandidates) {
        if ($existing -notcontains $candidate) {
            $env:PATH = "$candidate;$env:PATH"
        }
    }
}

function Set-GStreamerRuntime {
    param(
        [string]$RepoRoot
    )

    $scannerPath = Join-Path $RepoRoot ".local\\msys64\\ucrt64\\libexec\\gstreamer-1.0\\gst-plugin-scanner.exe"
    $pluginPath = Join-Path $RepoRoot ".local\\msys64\\ucrt64\\lib\\gstreamer-1.0"

    if (Test-Path $scannerPath) {
        $env:GST_PLUGIN_SCANNER = $scannerPath
    }

    if (Test-Path $pluginPath) {
        $env:GST_PLUGIN_SYSTEM_PATH_1_0 = $pluginPath
    }
}

function Resolve-PythonRuntime {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return @{
            FilePath = $python.Source
            PrefixArgs = @()
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{
            FilePath = $pyLauncher.Source
            PrefixArgs = @("-3")
        }
    }

    throw "Python 3 not found. Install Python or MSYS2 python to use the BLE beacon."
}

function Get-BonjourService {
    Get-Service | Where-Object {
        $_.DisplayName -eq "Bonjour Service" -or $_.Name -match "bonjour"
    } | Select-Object -First 1
}

function Get-PreferredIpv4Address {
    $netIpCommand = Get-Command Get-NetIPAddress -ErrorAction SilentlyContinue
    if ($netIpCommand) {
        $candidate = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object {
                $_.IPAddress -notlike "127.*" -and
                $_.IPAddress -notlike "169.254.*" -and
                $_.SkipAsSource -ne $true
            } |
            Sort-Object InterfaceMetric, SkipAsSource |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.IPAddress
        }
    }

    $dnsAddresses = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
        Where-Object {
            $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
            $_.IPAddressToString -notlike "127.*" -and
            $_.IPAddressToString -notlike "169.254.*"
        } |
        Select-Object -First 1

    if ($dnsAddresses) {
        return $dnsAddresses.IPAddressToString
    }

    throw "Unable to determine a usable IPv4 address. Pass -Ipv4Address explicitly."
}

function Get-DiscoveryMode {
    param(
        [switch]$ForceBleBeacon,
        [switch]$DisableBleBeacon
    )

    if ($ForceBleBeacon -and $DisableBleBeacon) {
        throw "Use either -UseBleBeacon or -SkipBleBeacon, not both."
    }

    if ($ForceBleBeacon) {
        return "ble"
    }

    $bonjour = Get-BonjourService
    if (-not $DisableBleBeacon -and (-not $bonjour -or $bonjour.Status -ne "Running")) {
        return "ble"
    }

    return "bonjour"
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeDir = Join-Path $repoRoot "runtime\windows-mirroring"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

$uxplayExe = Resolve-UxPlayPath -ExplicitPath $UxPlayPath -RepoRoot $repoRoot
Add-RuntimePath -RepoRoot $repoRoot -ExecutablePath $uxplayExe
Set-GStreamerRuntime -RepoRoot $repoRoot
$uxplayLogPath = Join-Path $runtimeDir "uxplay.log"
$beaconStdoutPath = Join-Path $runtimeDir "beacon.stdout.log"
$beaconStderrPath = Join-Path $runtimeDir "beacon.stderr.log"
$beaconScript = Join-Path $repoRoot "Bluetooth_LE_beacon\uxplay-beacon.py"

$discoveryMode = Get-DiscoveryMode -ForceBleBeacon:$UseBleBeacon -DisableBleBeacon:$SkipBleBeacon
$uxplayArgs = @("-n", $ServerName, "-nh", "-vs", $VideoSink, "-as", $AudioSink)
$beaconProcess = $null

if ($discoveryMode -eq "ble") {
    if (-not (Test-Path $beaconScript)) {
        throw "BLE beacon script not found at $beaconScript"
    }

    $pythonRuntime = Resolve-PythonRuntime
    if (-not $BleDataPath) {
        $BleDataPath = Join-Path $runtimeDir "uxplay.ble"
    }

    $resolvedIpv4 = if ($Ipv4Address) { $Ipv4Address } else { Get-PreferredIpv4Address }
    $beaconArgs = @()
    $beaconArgs += $pythonRuntime.PrefixArgs
    $beaconArgs += @($beaconScript, "--path", $BleDataPath, "--ipv4", $resolvedIpv4)

    Write-Host "Discovery: Bluetooth LE beacon ($resolvedIpv4)"
    $beaconProcess = Start-Process `
        -FilePath $pythonRuntime.FilePath `
        -ArgumentList $beaconArgs `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $beaconStdoutPath `
        -RedirectStandardError $beaconStderrPath `
        -PassThru

    $uxplayArgs += @("-ble", $BleDataPath)
}
else {
    $bonjour = Get-BonjourService
    if ($bonjour) {
        Write-Host "Discovery: Bonjour service ($($bonjour.Status))"
    }
    else {
        Write-Warning "Bonjour service not found. UxPlay will start, but iPhone discovery may fail."
    }
}

Write-Host "UxPlay: $uxplayExe"
Write-Host "Args: $($uxplayArgs -join ' ')"
Write-Host "Log: $uxplayLogPath"
Write-Host ""
Write-Host "On iPhone: open Control Center > Screen Mirroring > $ServerName"

try {
    $previousNativePreference = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $previousNativePreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }
    try {
        & $uxplayExe @uxplayArgs 2>&1 | Tee-Object -FilePath $uxplayLogPath
    }
    finally {
        if ($null -ne $previousNativePreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativePreference
        }
    }
}
finally {
    if ($beaconProcess -and -not $beaconProcess.HasExited) {
        Stop-Process -Id $beaconProcess.Id -Force
    }

    if ($BleDataPath -and (Test-Path $BleDataPath)) {
        Remove-Item $BleDataPath -Force -ErrorAction SilentlyContinue
    }
}
