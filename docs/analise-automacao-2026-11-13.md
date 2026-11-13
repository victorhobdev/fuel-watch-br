# Análise da automação do Fuel Watch BR

Data: 13/11/2026. Escopo: revisão das últimas execuções e alternativas ao controle pelo navegador. Nenhuma carga, instalação, novo login ou criação de recurso foi realizada nesta análise.

## Diagnóstico pelas evidências

O componente SQL M05 foi executado no Warehouse: erro 51999 após escritas, rollback confirmado por seis guards e recuperação reconciliada. A validação está em [sql-component-2026-11-13/validation.json](../evidence/fabric/orchestration/sql-component-2026-11-13/validation.json).

O primeiro mestre executado passou por Capture_Baseline, Copy_ANP, Bronze e Silver. A exportação falhou em `child_summary`, ao exigir exatamente um recibo novo descoberto por `Path.glob`. A Bronze devolveu 422.418 linhas e o identificador raiz correto. O endpoint SQL mostrou um novo manifesto de transferência, e o guard confirmou a publicação Gold anterior sem diferenças. Evidências em [pipeline-runs](../evidence/fabric/orchestration/pipeline-runs).

Isso localiza o problema na comunicação/descoberta do recibo. Cache do caminho montado é uma hipótese, ainda sem reprodução conclusiva no Fabric. Existe um teste local que simula listagem montada desatualizada; ele está vermelho e a correção continua pendente. Trocar a ferramenta de controle não resolve esse defeito de integração por si só.

O controle da interface acrescentou falhas independentes: carregamento intermitente, controles em vários iframes, atualização dos IDs acessíveis, colagem inteligente pendente e divergência entre copiar por botão e ler a área de transferência da automação. Comparar somente o clipboard com o texto recém-colado é evidência insuficiente quando o próprio mecanismo de colagem abastece esse clipboard. A próxima verificação de código deve comparar a definição devolvida pelo serviço com o arquivo local.

A última edição do notebook 08 foi interrompida durante a reprodução isolada. Antes de qualquer execução, sua definição remota e os parâmetros temporários precisam ser lidos e reconciliados com uma versão local revisada. Não há execução dessa reprodução confirmada nas evidências preservadas.

## Alternativas e escolha recomendada

| Caminho | Aplicação no projeto | Situação verificada |
| --- | --- | --- |
| Fabric CLI e REST API | Ler/publicar definições completas; executar e monitorar jobs; automatizar coleta de evidências | Azure CLI instalado; `fab` ainda não instalado; autenticação Fabric não validada |
| SQL direto por SQLCMD/ODBC | Executar arquivos T-SQL e guardar resultados e erros estruturados | `sqlcmd` e ODBC Drivers 17/18 instalados; conexão ao Warehouse não testada nesta análise |
| OneLake API/SDK | Upload de insumos e leitura de auditorias por caminho exato | Interface oficial disponível; acesso local ainda não autenticado/testado |
| Microsoft Fabric MCP Server | Expor operações e contratos Fabric como ferramentas do agente | Projeto oficial encontrado; nenhum servidor Fabric operacional conectado nesta sessão |
| Fabric RTI MCP | Consultas KQL e operações RTI no futuro M10 | Projeto oficial encontrado; não instalado nem conectado |
| Navegador | Experimentos da interface, configuração que exigir portal e verificação visual | Usar de forma pontual; evitar edição repetitiva de código e extração de resultados pela tela |

Recomendação operacional: começar com **CLI/API + SQL direto**, aproveitando o terminal já disponível. Acrescentar o MCP oficial quando a identidade e os acessos tiverem passado pelo teste de conexão. São acessos complementares; um MCP instalado ainda precisa de autenticação e de testes reais das ferramentas.

Na busca do catálogo de plugins não apareceu um conector pronto para administrar notebooks e pipelines; o resultado Power BI descreve trabalho pelo navegador e não elimina esse gargalo. A busca não prova ausência em todos os catálogos existentes.

## Ambiente e autenticação

- Python e Azure CLI instalados; Node v22.22.2 e `uv` disponíveis.
- SQLCMD e drivers ODBC 17/18 instalados. `pyodbc`, `azure.identity` e `msal` não estavam disponíveis no Python consultado.
- `az account show` conseguiu ler o contexto armazenado. O tenant corresponde ao observado no Fabric, mas a identidade selecionada não corresponde à conta Fabric usada nas execuções.
- Um GET de leitura dos itens do workspace pela API pública falhou antes de listar itens, com `AADSTS700082`. Esse código indica refresh token expirado por inatividade. Acesso API funcional permanece **não validado**.
- Não houve tentativa de login interativo, consentimento novo, alteração de permissões ou exposição de tokens. O primeiro acesso ao cache CLI falhou por restrição do sandbox; a leitura autorizada fora desse limite funcionou. Isso é separado da expiração de autenticação.

O primeiro passo da futura configuração deve ser autenticar a conta organizacional correta e validar acesso ao workspace. Para o laboratório, identidade de usuário é o ponto de partida; criar uma aplicação/service principal e distribuir segredos não é requisito inicial. Cada API continua sujeita a seus escopos e permissões.

As ferramentas locais não exigem criar nova capacidade Azure. As operações de dados continuam usando o trial existente e seus limites; não foi medido ganho de desempenho nem apresentado custo de recurso novo.

## Critério de aceite para a troca de acesso

1. Listar os itens do workspace pela API com a identidade esperada, sem imprimir credenciais.
2. Ler a definição remota do notebook 08, verificar a sintaxe de todas as células, conferir a célula de parâmetros e comparar o conteúdo com a versão local revisada. Preservar a definição anterior antes de atualizar.
3. Publicar a definição a partir do arquivo inteiro e reler para comparação; executar somente depois de confirmar essa correspondência.
4. Executar uma consulta SQL de leitura no Warehouse e salvar seu resultado. Não ampliar permissões se a conexão falhar; diagnosticar a identidade, autenticação e autorização.
5. Ler uma auditoria conhecida do OneLake por caminho exato. Evitar escolher simplesmente o arquivo mais recente.
6. Corrigir e provar a descoberta do recibo antes de retomar o mestre. Acompanhar o identificador do job até um estado terminal, respeitando `Retry-After` e sem reenviar jobs por timeout de observação.

Navegação, publicação de código, execução e validação são etapas diferentes. MCP/CLI não transformam uma resposta `202 Accepted` em execução bem-sucedida, nem eliminam a necessidade de reconciliar os dados.

## Fontes oficiais consultadas

- [Microsoft Fabric MCP Server](https://github.com/microsoft/mcp/blob/main/servers/Fabric.Mcp.Server/README.md): ferramentas operacionais autenticadas e documentação; configuração local por pacotes publicados.
- [Fabric CLI](https://microsoft.github.io/fabric-cli/), [autenticação](https://microsoft.github.io/fabric-cli/commands/auth/): operações via terminal e possibilidade de usar a sessão Azure CLI.
- [Update Notebook Definition](https://learn.microsoft.com/en-us/rest/api/fabric/notebook/items/update-notebook-definition): atualização de conteúdo em formato ipynb ou fabricGitSource.
- [Get Item Definition](https://learn.microsoft.com/en-us/rest/api/fabric/core/items/get-item-definition), [Run On Demand Item Job](https://learn.microsoft.com/en-us/rest/api/fabric/core/job-scheduler/run-on-demand-item-job): definições, permissões, operações assíncronas e acompanhamento de jobs.
- [Warehouse connectivity](https://learn.microsoft.com/en-us/fabric/data-warehouse/connectivity): protocolo TDS e autenticação Microsoft Entra.
- [OneLake API](https://learn.microsoft.com/en-us/fabric/onelake/onelake-access-api): compatibilidade com APIs/SDKs ADLS e Blob.
- [Fabric RTI MCP](https://github.com/microsoft/fabric-rti-mcp/): recursos de Eventhouse/KQL e outros serviços RTI, em preview.
- [Códigos Microsoft Entra](https://learn.microsoft.com/en-us/entra/identity-platform/reference-error-codes): significado de AADSTS700082.
