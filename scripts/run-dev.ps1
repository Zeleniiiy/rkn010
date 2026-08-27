[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [switch]$Execute,
    [switch]$OperatorMode,
    [int]$Limit = 0
)
& (Join-Path $PSScriptRoot "run.ps1") -Profile dev -Workbook $Workbook -Execute:$Execute -OperatorMode:$OperatorMode -Limit $Limit
exit $LASTEXITCODE

