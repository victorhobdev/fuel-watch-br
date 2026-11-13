$ErrorActionPreference = 'Stop'
$fuelCiRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $fuelCiRoot
try {
    # Recebe um Python ja preparado. Nao acessa Fabric, contas Azure ou dados ANP.
    if (-not $env:FUELWATCH_CI_PYTHON) { throw 'Defina FUELWATCH_CI_PYTHON com o Python do ambiente de CI.' }
    & $env:FUELWATCH_CI_PYTHON -m unittest tests.test_contract tests.test_versioning_lab tests.test_m05_stage tests.test_m05_shared_library tests.test_m05_resume tests.test_synthetic_events -v
    if ($LASTEXITCODE -ne 0) { throw 'Falha nos testes portaveis.' }
    & $env:FUELWATCH_CI_PYTHON -m unittest discover -s tools/fabric/tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Falha nos testes de transporte/isolamento de identidade.' }
} finally { Pop-Location }
