[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Profile,
    [string]$BaseUrl = "",
    [ValidateSet("requests", "curl")][string]$Transport = "requests",
    [switch]$NoVerifyTls,
    [string]$CaBundle = ""
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}

$arguments = @("-m", "rkn010_migration", "auth", "--profile", $Profile, "--transport", $Transport)
if ($BaseUrl) { $arguments += @("--base-url", $BaseUrl) }
if ($NoVerifyTls) { $arguments += "--no-verify-tls" }
if ($CaBundle) { $arguments += @("--ca-bundle", $CaBundle) }

Push-Location $repositoryRoot
try {
    & $pythonPath @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
