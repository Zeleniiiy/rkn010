[CmdletBinding()]
param(
    [string]$Profile = "custom",
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$State,
    [switch]$NoVerifyTls,
    [string]$CaBundle = "",
    [switch]$Execute
)
& (Join-Path $PSScriptRoot "rollback.ps1") -Profile $Profile -BaseUrl $BaseUrl -State $State -Transport curl -NoVerifyTls:$NoVerifyTls -CaBundle $CaBundle -Execute:$Execute
exit $LASTEXITCODE
