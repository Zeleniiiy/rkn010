[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [switch]$Execute,
    [switch]$ConfirmProd,
    [switch]$OperatorMode,
    [switch]$AllowOrgNameMismatch,
    [string]$Ogrn = "",
    [int]$Limit = 0
)
& (Join-Path $PSScriptRoot "run.ps1") -Profile prod -Workbook $Workbook -Transport curl -Execute:$Execute -ConfirmProd:$ConfirmProd -OperatorMode:$OperatorMode -AllowOrgNameMismatch:$AllowOrgNameMismatch -Ogrn $Ogrn -Limit $Limit
exit $LASTEXITCODE
