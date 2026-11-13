$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '../..')
try {
    uv venv .local/fabric-tools --python 3.13 --no-managed-python --cache-dir .local/uv-cache
    if ($LASTEXITCODE) { throw 'Falha ao criar venv.' }
    uv pip sync tools/fabric/requirements.lock --python .local/fabric-tools/Scripts/python.exe --cache-dir .local/uv-cache
    if ($LASTEXITCODE) { throw 'Falha ao instalar dependencias Python.' }
    npm.cmd install --prefix .local/fabric-mcp --save-exact '@microsoft/fabric-mcp@1.8.0' --cache .local/npm-cache --registry https://registry.npmjs.org --no-fund --no-audit
    if ($LASTEXITCODE) { throw 'Falha ao instalar MCP.' }
} finally {
    Pop-Location
}
