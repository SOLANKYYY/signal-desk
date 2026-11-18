$ErrorActionPreference = 'Stop'
# Fixture cmdlets keep this test from reading the actual laptop.
function Get-MpComputerStatus { [pscustomobject]@{ AntivirusEnabled=$true; RealTimeProtectionEnabled=$false; AntivirusSignatureAge=9; QuickScanAge=1; ComputerID='DO-NOT-COLLECT' } }
function Get-NetFirewallProfile { @([pscustomobject]@{Name='Public';Enabled=0},[pscustomobject]@{Name='Private';Enabled=1},[pscustomobject]@{Name='Domain';Enabled=2}) }
function Get-MpThreat { @([pscustomobject]@{ IsActive=$true; Resources='SECRET-PATH' },[pscustomobject]@{ IsActive=$false }) }
function Get-HotFix { [pscustomobject]@{ InstalledOn=[datetime]'2026-10-01'; InstalledBy='DO-NOT-COLLECT' } }
function Confirm-SecureBootUEFI { throw 'Unavailable test fixture' }
function Get-BitLockerVolume { [pscustomobject]@{ProtectionStatus=1;KeyProtector='SECRET-KEY'} }
function Get-ItemProperty { [pscustomobject]@{ fDenyTSConnections=1 } }
$out = Join-Path $env:TEMP ('signal-desk-fixture-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    & (Join-Path $PSScriptRoot '..\tools\Collect-SignalDeskCheck.ps1') -OutputPath $out
    $text = Get-Content -LiteralPath $out -Raw
    $r = $text | ConvertFrom-Json
    if ($r.checks.threats.active_count -ne 1 -or $r.checks.threats.history_count -ne 2) { throw 'Threat fixture mismatch' }
    if ($r.checks.firewall.public_enabled -ne $false -or $r.checks.firewall.private_enabled -ne $true -or $null -ne $r.checks.firewall.domain_enabled) { throw 'Firewall states mismatch' }
    if ($r.checks.secure_boot.available -ne $false) { throw 'Failed check must be unavailable' }
    if ($text -match 'SECRET|DO-NOT-COLLECT') { throw 'Collector leaked excluded fixture fields' }
    $refused=$false
    try { & (Join-Path $PSScriptRoot '..\tools\Collect-SignalDeskCheck.ps1') -OutputPath $out } catch { $refused=$true }
    if (-not $refused) { throw 'Collector overwrote an existing report' }
    foreach ($mode in @('denied','empty','unknown')) {
        Remove-Item -LiteralPath $out
        function Get-BitLockerVolume {
            [CmdletBinding()]param([string]$MountPoint)
            if ($mode -eq 'denied') { Write-Error 'Access denied fixture'; return }
            if ($mode -eq 'empty') { return $null }
            return [pscustomobject]@{ProtectionStatus=2}
        }
        & (Join-Path $PSScriptRoot '..\tools\Collect-SignalDeskCheck.ps1') -OutputPath $out
        $r = Get-Content -LiteralPath $out -Raw | ConvertFrom-Json
        if ($r.checks.disk_encryption.available -ne $false -or $null -ne $r.checks.disk_encryption.enabled) { throw "Unavailable BitLocker was treated as a known state: $mode" }
    }
    Write-Host 'Collector fixture tests passed; actual device settings were not read.'
} finally { if (Test-Path -LiteralPath $out) { Remove-Item -LiteralPath $out } }
