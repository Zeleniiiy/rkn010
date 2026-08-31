[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$State,
    [switch]$Execute,
    [switch]$ConfirmProd
)
& (Join-Path $PSScriptRoot "rollback.ps1") -Profile prod -State $State -Transport curl -Execute:$Execute -ConfirmProd:$ConfirmProd
exit $LASTEXITCODE
