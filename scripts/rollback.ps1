[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Profile,
    [Parameter(Mandatory = $true)][string]$State,
    [string]$BaseUrl = "",
    [ValidateSet("requests", "curl")][string]$Transport = "requests",
    [switch]$NoVerifyTls,
    [string]$CaBundle = "",
    [switch]$Execute,
    [switch]$ConfirmProd
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}
if (-not (Test-Path -LiteralPath $State)) {
    throw "Checkpoint not found: $State"
}

$arguments = @("-m", "rkn010_migration", "rollback", "--profile", $Profile, "--state", $State, "--transport", $Transport)
if ($BaseUrl) { $arguments += @("--base-url", $BaseUrl) }
if ($NoVerifyTls) { $arguments += "--no-verify-tls" }
if ($CaBundle) { $arguments += @("--ca-bundle", $CaBundle) }
if ($Execute) { $arguments += "--execute" }
if ($ConfirmProd) { $arguments += "--confirm-prod" }

Push-Location $repositoryRoot
try {
    & $pythonPath @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
