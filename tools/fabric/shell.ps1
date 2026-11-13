# Execute com: . ./tools/fabric/shell.ps1
$fuelRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$env:AZURE_CONFIG_DIR = Join-Path $fuelRoot '.local/azure'
$env:FUELWATCH_IDENTITY = 'author'
New-Item -ItemType Directory -Force $env:AZURE_CONFIG_DIR | Out-Null
$env:PATH = (Join-Path $fuelRoot '.local/fabric-tools/Scripts') + ';' + $env:PATH
Write-Host 'Ferramentas Fuel Watch carregadas; login Azure isolado em .local/azure.'
