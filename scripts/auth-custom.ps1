[CmdletBinding()]
param(
    [string]$Profile = "custom",
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [switch]$NoVerifyTls,
    [string]$CaBundle = ""
)
& (Join-Path $PSScriptRoot "auth.ps1") -Profile $Profile -BaseUrl $BaseUrl -Transport curl -NoVerifyTls:$NoVerifyTls -CaBundle $CaBundle
exit $LASTEXITCODE
