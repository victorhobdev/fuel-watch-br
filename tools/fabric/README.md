# Ferramentas operacionais do Fuel Watch BR

Instaladas em `.local/`, fora do Git e do runtime Spark do Fabric.

| Componente | Versao validada | Uso |
|---|---|---|
| Fabric CLI | 1.9.0 | REST, itens e jobs |
| Fabric MCP oficial | 1.8.0 | Operacoes assistidas via STDIO |
| azure-identity | 1.27.0 | Tokens Entra |
| azure-storage-file-datalake | 12.26.1 | OneLake |
| pyodbc | 5.5.0 | Warehouse TDS |
| ODBC Driver | 18, existente | Conexao SQL Entra |

## Uso

Execute no PowerShell, a partir da raiz do repositorio:

```powershell
. ./tools/fabric/shell.ps1
fab --version
az login --tenant <tenant-do-projeto> --allow-no-subscriptions --use-device-code
fab auth login --azure-cli
```

O cache Azure deste shell fica em `.local/azure`. Isso preserva o login Azure global. Fabric CLI 1.9.0 usa sua propria configuracao padrao em `~/.config/fab`; nao foi alterado HOME nem modificado o pacote para contornar esse comportamento.

`install.ps1` reproduz as dependencias em maquina com Python 3.13, uv e Node 22+ existentes. `requirements.lock` fixa as dependencias Python. O MCP usa pacote oficial com versao fixa.

## MCP no Codex

A configuracao desta maquina esta em `.codex/config.toml`, ignorada pelo Git. Usa STDIO local, namespaces core/jobs/onelake e uma lista explicita de ferramentas para consultar itens, obter/atualizar definicoes, acompanhar/executar jobs e ler arquivos. Cada ferramenta solicita aprovacao; ferramentas de exclusao de itens e alteracao de permissoes nao foram habilitadas.

`codex mcp get fabric` confirmou o registro. O chat atual ainda nao recebeu as ferramentas dinamicamente: reiniciar a sessao do Codex pode ser necessario para carrega-las. A CLI/REST continua disponivel sem essa dependencia.

```powershell
.local/fabric-tools/Scripts/python.exe tools/fabric/probe_mcp.py
```

O probe testa initialize/list_tools, sem executar operacoes remotas. Seu resultado fica em `.local/fabric-mcp-probe.json`. Sucesso de protocolo nao comprova autenticacao nem acesso ao Fabric.

## Estado verificado em 2026-11-13

- Instalacao Python, imports e drivers ODBC: validados.
- Fabric CLI `--version`: validado.
- MCP initialize/list_tools: validado, servidor 1.8.0.
- Registro MCP local: validado por `codex mcp get fabric`.
- Login no cache isolado: concluido pelo usuario. Fabric CLI recebeu login via Azure CLI.
- REST: lista real de itens do workspace validada. OneLake: listagem real de Files validada. SQL: SELECT 1 no Warehouse validado com token Entra. Evidencia: evidence/fabric/tooling/setup-2026-11-13.json.
- Nenhum job de dados ou recurso Azure pago foi criado por esta configuracao.

Antes de retomar M05: obter e preservar a definicao remota do notebook 08, comparar com o fonte local e corrigir a descoberta de recibos. O ultimo teste local dessa area ainda tem uma falha conhecida; instalacao das ferramentas nao resolve nem valida esse comportamento.

Referencias: [Fabric CLI](https://microsoft.github.io/fabric-cli/), [Microsoft Fabric MCP](https://github.com/microsoft/mcp/blob/main/servers/Fabric.Mcp.Server/README.md), [Codex MCP](https://developers.openai.com/codex/mcp/).

