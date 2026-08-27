[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [switch]$Execute,
    [switch]$ConfirmProd,
    [switch]$OperatorMode,
    [int]$Limit = 0
)
& (Join-Path $PSScriptRoot "run.ps1") -Profile prod -Workbook $Workbook -Execute:$Execute -ConfirmProd:$ConfirmProd -OperatorMode:$OperatorMode -Limit $Limit
exit $LASTEXITCODE

