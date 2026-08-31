[CmdletBinding()]
param()
& (Join-Path $PSScriptRoot "auth.ps1") -Profile prod -Transport curl
exit $LASTEXITCODE
