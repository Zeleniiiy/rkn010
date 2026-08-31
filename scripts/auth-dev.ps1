[CmdletBinding()]
param()
& (Join-Path $PSScriptRoot "auth.ps1") -Profile dev -Transport curl
exit $LASTEXITCODE
