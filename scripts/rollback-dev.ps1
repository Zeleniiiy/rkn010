[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$State,
    [switch]$Execute
)
& (Join-Path $PSScriptRoot "rollback.ps1") -Profile dev -State $State -Transport curl -Execute:$Execute
exit $LASTEXITCODE
