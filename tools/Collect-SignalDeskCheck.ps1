# Signal Desk: read-only Windows security snapshot. Review this script before running.
# Does not scan files, upload data, install software, change settings or collect
# usernames, hostnames, IP addresses, file paths, passwords or recovery keys.
# Run from Windows PowerShell. Some checks need Run as administrator; failed
# checks are recorded as unavailable, never as passing. Only output is a JSON file.
param([string]$OutputPath = (Join-Path (Get-Location) ('SignalDesk-Device-Check-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')))
$ErrorActionPreference = 'Stop'
function Read-Bool($Value) {
    if ($null -eq $Value) { return $null }
    return [bool]$Value
}
function Read-Age($Value) {
    if ($null -eq $Value -or [double]$Value -lt 0 -or [double]$Value -gt 36500) { return $null }
    return [int]$Value
}
$checks = [ordered]@{}
try {
    $d = Get-MpComputerStatus
    $checks.defender = @{ available=$true; antivirus_enabled=(Read-Bool $d.AntivirusEnabled); real_time_enabled=(Read-Bool $d.RealTimeProtectionEnabled); signature_age_days=(Read-Age $d.AntivirusSignatureAge); quick_scan_age_days=(Read-Age $d.QuickScanAge) }
} catch { $checks.defender = @{ available=$false } }
try {
    $profiles = @(Get-NetFirewallProfile)
    $f = @{ available=$true; domain_enabled=$null; private_enabled=$null; public_enabled=$null }
    foreach ($profile in $profiles) {
        $key = ([string]$profile.Name).ToLower() + '_enabled'
        if ($f.ContainsKey($key) -and $null -ne $profile.Enabled) {
            if ([int]$profile.Enabled -eq 1) { $f[$key] = $true }
            elseif ([int]$profile.Enabled -eq 0) { $f[$key] = $false }
        }
    }
    $checks.firewall = $f
} catch { $checks.firewall = @{ available=$false } }
try {
    $threats = @(Get-MpThreat)
    $checks.threats = @{ available=$true; active_count=@($threats | Where-Object { $_.IsActive -eq $true }).Count; history_count=$threats.Count }
} catch { $checks.threats = @{ available=$false } }
try {
    $dates = @(Get-HotFix | Where-Object { $null -ne $_.InstalledOn } | Sort-Object InstalledOn -Descending)
    $lastDate = $null
    if ($dates.Count -gt 0) { $lastDate = ([datetime]$dates[0].InstalledOn).ToString('yyyy-MM-dd') }
    $checks.updates = @{ available=$true; last_hotfix_date=$lastDate }
} catch { $checks.updates = @{ available=$false } }
try {
    $secure = Confirm-SecureBootUEFI
    $checks.secure_boot = @{ available=$true; enabled=[bool]$secure }
} catch { $checks.secure_boot = @{ available=$false } }
try {
    $bitErrors = @()
    $volume = Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction Stop -ErrorVariable bitErrors 2>$null
    if ($bitErrors.Count -gt 0 -or $null -eq $volume -or $null -eq $volume.ProtectionStatus -or [int]$volume.ProtectionStatus -notin @(0,1)) {
        throw 'BitLocker status unavailable.'
    }
    $checks.disk_encryption = @{ available=$true; enabled=([int]$volume.ProtectionStatus -eq 1) }
} catch { $checks.disk_encryption = @{ available=$false } }
try {
    $v = Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections
    $checks.remote_desktop = @{ available=$true; enabled=([int]$v.fDenyTSConnections -eq 0) }
} catch { $checks.remote_desktop = @{ available=$false } }
# Inventory selected software families; no installation paths or personal names
# are written to the report. This is not a complete application/CVE inventory.
$softwareItems = @()
try {
    $locations = @('HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*','HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*')
    $installed = @(Get-ItemProperty -Path $locations -ErrorAction SilentlyContinue)
    foreach ($app in $installed) {
        $product = $null; $candidates = @()
        switch -Regex ($app.DisplayName) {
            '^Java 8 Update \d+' { if ($app.Publisher -like '*Oracle*') { $product='oracle_java_8'; if ($app.InstallLocation) { $candidates=@((Join-Path $app.InstallLocation 'bin\java.exe')) } } }
            '^TeamViewer( Host)?$' { $product='teamviewer'; $candidates=@('C:\Program Files\TeamViewer\TeamViewer_Service.exe','C:\Program Files (x86)\TeamViewer\TeamViewer_Service.exe') }
            '^Google Chrome$' { $product='chrome' }
            '^Microsoft Edge$' { $product='edge' }
            '^Git$' { $product='git' }
            '^NVIDIA Graphics Driver ' { $product='nvidia_driver' }
            '^HP Connection Optimizer$' { $product='hp_connection_optimizer' }
        }
        if (-not $product -or [string]$app.DisplayVersion -notmatch '^\d{1,6}(\.\d{1,6}){1,3}$') { continue }
        $version=[string]$app.DisplayVersion; $evidence='registry'
        foreach ($candidate in $candidates) {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $fileVersion=(Get-Item -LiteralPath $candidate).VersionInfo.FileVersion
                if ($fileVersion -match '^\d{1,6}(\.\d{1,6}){1,3}$') { $version=$fileVersion; $evidence='file_version'; break }
            }
        }
        $softwareItems += @{ product=$product; version=$version; evidence=$evidence }
    }
    $software=@{ available=$true; collected_at=[DateTime]::UtcNow.ToString('o'); items=@($softwareItems | Sort-Object { $_.product },{ $_.version } -Unique) }
} catch { $software=@{ available=$false; items=@() } }
$report = [ordered]@{ schema='signal-desk-device-check/v1'; generated_at=[DateTime]::UtcNow.ToString('o'); checks=$checks; software=$software }
if (Test-Path -LiteralPath $OutputPath) { throw 'Output already exists. Choose a new -OutputPath to preserve it.' }
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Saved security snapshot to: $OutputPath"
if (-not $checks.disk_encryption.available) { Write-Host 'BitLocker status unavailable (permissions or Windows support). It will be reported as unknown.' }
Write-Host 'Review the JSON, then attach it in Signal Desk > Ask Signal Desk > Check my laptop.'
Write-Host 'No data was uploaded. This snapshot cannot prove whether an attack is happening.'
