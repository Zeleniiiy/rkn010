[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $repositoryRoot ".venv"
$pythonPath = Join-Path $venvPath "Scripts\python.exe"

foreach ($profile in @("dev", "psi", "prod", "custom")) {
    $authDirectory = Join-Path $repositoryRoot "auth\$profile"
    New-Item -ItemType Directory -Path $authDirectory -Force | Out-Null
    foreach ($fileName in @("token.md", "cookie.md")) {
        $authFile = Join-Path $authDirectory $fileName
        if (-not (Test-Path -LiteralPath $authFile)) {
            New-Item -ItemType File -Path $authFile | Out-Null
        }
    }

    $inputDirectory = Join-Path $repositoryRoot "input\$profile"
    New-Item -ItemType Directory -Path $inputDirectory -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv $venvPath
}

& $pythonPath -m pip install --upgrade pip
& $pythonPath -m pip install -r (Join-Path $repositoryRoot "requirements.txt")
& $pythonPath -m pytest
