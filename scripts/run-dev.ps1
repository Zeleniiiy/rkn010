[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [switch]$Execute,
    [switch]$OperatorMode,
    [switch]$AllowOrgNameMismatch,
    [string]$Ogrn = "",
    [int]$Limit = 0
)
& (Join-Path $PSScriptRoot "run.ps1") -Profile dev -Workbook $Workbook -Transport curl -Execute:$Execute -OperatorMode:$OperatorMode -AllowOrgNameMismatch:$AllowOrgNameMismatch -Ogrn $Ogrn -Limit $Limit
exit $LASTEXITCODE
