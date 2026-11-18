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
$report = [ordered]@{ schema='signal-desk-device-check/v1'; generated_at=[DateTime]::UtcNow.ToString('o'); checks=$checks }
if (Test-Path -LiteralPath $OutputPath) { throw 'Output already exists. Choose a new -OutputPath to preserve it.' }
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
Write-Host "Saved security snapshot to: $OutputPath"
if (-not $checks.disk_encryption.available) { Write-Host 'BitLocker status unavailable (permissions or Windows support). It will be reported as unknown.' }
Write-Host 'Review the JSON, then attach it in Signal Desk > Ask Signal Desk > Check my laptop.'
Write-Host 'No data was uploaded. This snapshot cannot prove whether an attack is happening.'
