[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Workbook,
    [switch]$Execute,
    [switch]$OperatorMode,
    [switch]$AllowOrgNameMismatch,
    [string]$Ogrn = "",
    [int]$Limit = 0
)
& (Join-Path $PSScriptRoot "run.ps1") -Profile psi -BaseUrl "https://psi.pgs.gosuslugi.ru" -Workbook $Workbook -Transport curl -NoVerifyTls -Execute:$Execute -OperatorMode:$OperatorMode -AllowOrgNameMismatch:$AllowOrgNameMismatch -Ogrn $Ogrn -Limit $Limit
exit $LASTEXITCODE
