[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$State,
    [switch]$Execute
)
& (Join-Path $PSScriptRoot "rollback.ps1") -Profile psi -BaseUrl "https://psi.pgs.gosuslugi.ru" -State $State -Transport curl -NoVerifyTls -Execute:$Execute
exit $LASTEXITCODE
