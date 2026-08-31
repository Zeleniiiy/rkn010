[CmdletBinding()]
param()
& (Join-Path $PSScriptRoot "auth.ps1") -Profile psi -BaseUrl "https://psi.pgs.gosuslugi.ru" -Transport curl -NoVerifyTls
exit $LASTEXITCODE
