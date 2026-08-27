[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("dev", "psi", "prod")]
    [string]$Profile,
    [Parameter(Mandatory = $true)]
    [string]$Workbook,
    [switch]$Execute,
    [switch]$ConfirmProd,
    [switch]$OperatorMode,
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Virtual environment not found. Run scripts\bootstrap.ps1 first."
}

$arguments = @(
    "-m", "rkn010_migration", "run",
    "--profile", $Profile,
    "--workbook", $Workbook,
    "--workdir", (Join-Path $repositoryRoot "runs")
)
if ($Execute) { $arguments += "--execute" }
if ($ConfirmProd) { $arguments += "--confirm-prod" }
if ($OperatorMode) { $arguments += "--operator-mode" }
if ($Limit -gt 0) { $arguments += @("--limit", $Limit) }

Push-Location $repositoryRoot
try {
    & $pythonPath @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
