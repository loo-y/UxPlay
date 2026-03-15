[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$repoRoot = Split-Path -Parent $PSScriptRoot
$settingsDir = Join-Path $repoRoot "runtime\windows-mirroring"
$settingsPath = Join-Path $settingsDir "launcher-settings.json"
$runScript = Join-Path $repoRoot "scripts\run-uxplay-windows.cmd"

if (-not (Test-Path $settingsDir)) {
    New-Item -ItemType Directory -Path $settingsDir | Out-Null
}

function Get-LauncherSettings {
    if (-not (Test-Path $settingsPath)) {
        return @{
            server_name = "UxPlay-Windows"
            topmost = $true
        }
    }

    try {
        $loaded = Get-Content $settingsPath -Raw | ConvertFrom-Json
        return @{
            server_name = if ([string]::IsNullOrWhiteSpace($loaded.server_name)) { "UxPlay-Windows" } else { [string]$loaded.server_name }
            topmost = if ($null -eq $loaded.topmost) { $true } else { [bool]$loaded.topmost }
        }
    } catch {
        return @{
            server_name = "UxPlay-Windows"
            topmost = $true
        }
    }
}

function Save-LauncherSettings([string]$serverName, [bool]$topmost) {
    $payload = @{
        server_name = $serverName
        topmost = $topmost
    } | ConvertTo-Json
    Set-Content -Path $settingsPath -Value $payload -Encoding UTF8
}

function Stop-UxPlayWindows {
    Get-Process uxplay -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*keep-uxplay-topmost.ps1*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like '*run-uxplay-windows.cmd*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Start-UxPlayWindows([string]$serverName, [bool]$topmost) {
    Stop-UxPlayWindows

    $cmdArgs = @("/k", ".\scripts\run-uxplay-windows.cmd", "--name", $serverName)
    if (-not $topmost) {
        $cmdArgs += "--no-topmost"
    }

    Start-Process -FilePath "cmd.exe" -WorkingDirectory $repoRoot -ArgumentList $cmdArgs | Out-Null
}

$settings = Get-LauncherSettings

$form = New-Object System.Windows.Forms.Form
$form.Text = "UxPlay Launcher"
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.ClientSize = New-Object System.Drawing.Size(420, 215)

$nameLabel = New-Object System.Windows.Forms.Label
$nameLabel.Text = "Device Name"
$nameLabel.Location = New-Object System.Drawing.Point(18, 22)
$nameLabel.AutoSize = $true
$form.Controls.Add($nameLabel)

$nameTextBox = New-Object System.Windows.Forms.TextBox
$nameTextBox.Location = New-Object System.Drawing.Point(18, 46)
$nameTextBox.Size = New-Object System.Drawing.Size(380, 24)
$nameTextBox.Text = $settings.server_name
$form.Controls.Add($nameTextBox)

$topmostCheckbox = New-Object System.Windows.Forms.CheckBox
$topmostCheckbox.Location = New-Object System.Drawing.Point(18, 84)
$topmostCheckbox.Size = New-Object System.Drawing.Size(220, 24)
$topmostCheckbox.Text = "Keep mirror window topmost"
$topmostCheckbox.Checked = $settings.topmost
$form.Controls.Add($topmostCheckbox)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Location = New-Object System.Drawing.Point(18, 120)
$statusLabel.Size = New-Object System.Drawing.Size(380, 34)
$statusLabel.Text = "Saved settings load automatically. Start opens the normal UxPlay console window."
$form.Controls.Add($statusLabel)

$saveButton = New-Object System.Windows.Forms.Button
$saveButton.Location = New-Object System.Drawing.Point(18, 165)
$saveButton.Size = New-Object System.Drawing.Size(90, 30)
$saveButton.Text = "Save"
$form.Controls.Add($saveButton)

$startButton = New-Object System.Windows.Forms.Button
$startButton.Location = New-Object System.Drawing.Point(214, 165)
$startButton.Size = New-Object System.Drawing.Size(88, 30)
$startButton.Text = "Start"
$form.Controls.Add($startButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Location = New-Object System.Drawing.Point(310, 165)
$stopButton.Size = New-Object System.Drawing.Size(88, 30)
$stopButton.Text = "Stop"
$form.Controls.Add($stopButton)

$saveAction = {
    $serverName = $nameTextBox.Text.Trim()
    if ([string]::IsNullOrWhiteSpace($serverName)) {
        [System.Windows.Forms.MessageBox]::Show("Device name cannot be empty.", "UxPlay Launcher") | Out-Null
        return $false
    }
    Save-LauncherSettings -serverName $serverName -topmost $topmostCheckbox.Checked
    $statusLabel.Text = "Settings saved."
    return $true
}

$saveButton.Add_Click({
    & $saveAction | Out-Null
})

$startButton.Add_Click({
    if (-not (& $saveAction)) {
        return
    }
    Start-UxPlayWindows -serverName $nameTextBox.Text.Trim() -topmost $topmostCheckbox.Checked
    $statusLabel.Text = "UxPlay started. Connect from iPhone Screen Mirroring."
})

$stopButton.Add_Click({
    Stop-UxPlayWindows
    $statusLabel.Text = "UxPlay stopped."
})

[void]$form.ShowDialog()
