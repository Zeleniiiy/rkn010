[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Profile,
    [Parameter(Mandatory = $true)]
    [string]$Workbook,
    [string]$BaseUrl = "",
    [ValidateSet("requests", "curl")]
    [string]$Transport = "requests",
    [switch]$NoVerifyTls,
    [string]$CaBundle = "",
    [switch]$Execute,
    [switch]$ConfirmProd,
    [switch]$OperatorMode,
    [switch]$AllowOrgNameMismatch,
    [string]$Ogrn = "",
    [string]$Zone = "",
    [string]$Workdir = "",
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}
$resolvedWorkdir = if ($Workdir) { $Workdir } else { Join-Path $repositoryRoot "runs" }

$arguments = @(
    "-m", "rkn010_migration", "run",
    "--profile", $Profile,
    "--workbook", $Workbook,
    "--workdir", $resolvedWorkdir,
    "--transport", $Transport
)
if ($BaseUrl) { $arguments += @("--base-url", $BaseUrl) }
if ($NoVerifyTls) { $arguments += "--no-verify-tls" }
if ($CaBundle) { $arguments += @("--ca-bundle", $CaBundle) }
if ($Execute) { $arguments += "--execute" }
if ($ConfirmProd) { $arguments += "--confirm-prod" }
if ($OperatorMode) { $arguments += "--operator-mode" }
if ($AllowOrgNameMismatch) { $arguments += "--allow-org-name-mismatch" }
if ($Ogrn) { $arguments += @("--ogrn", $Ogrn) }
if ($Zone) { $arguments += @("--zone", $Zone) }
if ($Limit -gt 0) { $arguments += @("--limit", $Limit) }

Push-Location $repositoryRoot
try {
    & $pythonPath @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
