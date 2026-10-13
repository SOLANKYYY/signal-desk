# Run from this kit's folder after start.ps1. Requires Docker Desktop only.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$LabNetwork = 'signal-desk-exercise9-net'
$LabNodes = @('sd9-mongo1', 'sd9-mongo2', 'sd9-mongo3')
function Invoke-Lab([string[]]$LabArguments) {
    & docker compose run --rm -T python @LabArguments
    if ($LASTEXITCODE -ne 0) { throw "Lab command failed: $LabArguments" }
}
function Disconnect-LabNode([string]$LabNode) {
    if ($LabNode -notin $LabNodes) { throw 'Unexpected lab node' }
    & docker network disconnect $LabNetwork $LabNode
    if ($LASTEXITCODE -ne 0) { throw "Cannot disconnect $LabNode" }
}
function Restore-LabNetwork {
    $LabRestoreErrors = @()
    foreach ($LabNode in $LabNodes) {
        $LabInspect = & docker inspect $LabNode
        if ($LASTEXITCODE -ne 0) { $LabRestoreErrors += $LabNode; continue }
        $LabContainer = ($LabInspect | ConvertFrom-Json)[0]
        if (-not $LabContainer.NetworkSettings.Networks.PSObject.Properties[$LabNetwork]) {
            & docker network connect --alias $LabNode $LabNetwork $LabNode
            if ($LASTEXITCODE -ne 0) { $LabRestoreErrors += $LabNode }
        }
    }
    if ($LabRestoreErrors.Count) { throw "Reconnect failed for $LabRestoreErrors. See README recovery commands." }
}
try {
    Restore-LabNetwork
    Invoke-Lab -LabArguments @('init')
    Invoke-Lab -LabArguments @('partition-start')
    $LabPlan = Get-Content ./results/partition-plan.json -Raw | ConvertFrom-Json
    Disconnect-LabNode $LabPlan.secondaries[0]
    Invoke-Lab -LabArguments @('phase', 'one-secondary-offline', '30')
    Restore-LabNetwork
    Invoke-Lab -LabArguments @('recover', 'first-recovery')
    $LabPlan = Get-Content ./results/partition-plan.json -Raw | ConvertFrom-Json
    foreach ($LabNode in $LabPlan.secondaries) { Disconnect-LabNode $LabNode }
    Invoke-Lab -LabArguments @('phase', 'two-secondaries-offline', '30')
} finally {
    Restore-LabNetwork
}
Invoke-Lab -LabArguments @('recover', 'final-recovery')
Invoke-Lab -LabArguments @('finish')
