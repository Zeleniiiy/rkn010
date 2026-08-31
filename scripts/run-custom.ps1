[CmdletBinding()]
param(
    [string]$Profile = "custom",
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$Workbook,
    [switch]$Execute,
    [switch]$OperatorMode,
    [switch]$AllowOrgNameMismatch,
    [switch]$NoVerifyTls,
    [string]$CaBundle = "",
    [string]$Ogrn = "",
    [int]$Limit = 0
)
& (Join-Path $PSScriptRoot "run.ps1") -Profile $Profile -BaseUrl $BaseUrl -Workbook $Workbook -Transport curl -Execute:$Execute -OperatorMode:$OperatorMode -AllowOrgNameMismatch:$AllowOrgNameMismatch -NoVerifyTls:$NoVerifyTls -CaBundle $CaBundle -Ogrn $Ogrn -Limit $Limit
exit $LASTEXITCODE
