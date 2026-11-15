# Reconstrução da solução ampliada

Estado em 15/11/2026: reconstrução de dados e consumo executada em um workspace
que estava vazio, na mesma capacidade trial FTL4 do ambiente dev. Lakehouse e Warehouse foram
criados no destino; nenhum Delta nem recibo de dev foi copiado. Bronze, Silver,
Gold, contexto, modelo semântico e relatório foram gerados e reconciliados no
destino. A auditoria final confirmou dev, test e rebuild sem jobs, sessões Spark
ou agendas habilitadas. O pipeline integrado foi reconstruído no destino e a
repetição controlada completou Copy, validação Silver e verificação de publicação,
pulando a escrita da Gold idêntica. Os recibos da definição e do run estão em
`evidence/phase2/deployment/`. O CI do código corrigido passou e está registrado
em `evidence/phase2/deployment/github-ci.json`.

Bindings privados: `.local/phase2-rebuild/`; nunca substituir a configuração
padrão de desenvolvimento. Conferir ausência de IDs literais de dev nas células
e Lakehouse padrão do destino antes de iniciar Spark.

Dependências de bootstrap verificadas no código:

1. `01_landing_to_bronze`: requer o ZIP oficial preservado no landing, SHA
   aprovado e caminho de execução explícito. Produz `bronze_anp`.
2. `10_brasil_todos_combustiveis`: requer Bronze 2026H1 e bundle nacional
   imutável. Produz `silver_preco_brasil` e referências nacionais.
3. `11_historico_bronze_silver`: requer quatro ZIPs oficiais no landing por ID
   da execução, manifesto histórico, referências independentes e regras por hash.
4. `12_historico_publicacao`: consome Silver nacional e versões históricas,
   recalcula o conjunto conjunto e gera transferência aprovada para o Warehouse.
5. `15_context_references`: verifica hashes e publica população/clima no destino.

Somente arquivos imutáveis de entrada e referências de validação foram
transportados. Não copiaram-se tabelas Delta ou recibos de execução de dev para
apresentá-los como resultados reconstruídos. Cada job do destino gerou recibo
próprio e foi reconciliado antes de publicar Gold e análises.

## Resultado verificado no destino

- O workspace `fuelwatch-rebuild-f2` foi conferido vazio antes da criação; os
  recursos usam a capacidade FTL4 trial existente.
- Os cinco notebooks necessários foram executados serialmente. A publicação
  produziu 2.125.547 coletas, 13.030 CNPJs, 462 municípios, 27 UFs e seis
  produtos, mantendo o semestre 2026H1. Silver/Gold, SCD2, semanas ISO e
  projeções de negócio foram comparadas integralmente.
- População e clima foram carregados por hash. O join de contexto manteve
  2.125.547 linhas e o total de preços; quatro grupos populacionais e os limites
  de cobertura climática foram reconciliados.
- As sete análises históricas e o painel de postos comuns foram reconstruídos.
  O modelo DirectQuery passou em três recortes adicionais; o guard de contexto
  misto foi verificado. O PDF de quatro páginas foi exportado e inspecionado;
  a página de postos comuns mostra as 27 UFs sem rolagem.
- O runtime Fabric/Spark foi registrado nos recibos; os pacotes de CI, CLI e
  desenvolvimento local têm locks versionados. Os detalhes ficam em
  `evidence/phase2/deployment/`.

A promoção/restauração dev → test foi exercitada anteriormente no M08; o aceite
e os runs restaurados estão em `evidence/fabric/deployment/checkpoint.json`.
Essa evidência não significa que os dados do rebuild foram promovidos por essa
pipeline. A reconstrução limpa foi uma validação separada.

## Execução e parâmetros via API

A primeira tentativa de `01_landing_to_bronze` pela ferramenta genérica de job
do MCP aceitou a execução, mas não aplicou os parâmetros do notebook: a auditoria
Fabric registrou o caminho literal `EXECUTION_ID/ca-2026-01.zip` e terminou com
`FileNotFoundError`, antes de qualquer escrita Bronze. O job seguinte com o array
de parâmetros no formato da API genérica também deixou os valores padrão. Isso
foi confirmado pelo conteúdo real de `Files/audit/anp/79d52a14-e82f-44be-afb8-48a4c6ead220.json`.

Para as próximas etapas, o runner local usa a API específica de Notebook:
`POST /notebooks/{id}/jobs/execute/instances?beta=false`, com `parameters` no
nível superior e `executionData.computeConfiguration.defaultLakehouse` apontando
por ID para o Lakehouse de reconstrução. O runner verifica que não há sessão
Spark ativa, registra o recibo uma única vez, espera o `Retry-After` e acompanha
o mesmo `jobInstanceId`; nenhum POST é repetido automaticamente.

O workflow remoto `Fuel Watch checks` foi disparado para o commit
`3076cd4f594c5e301f3f697b798d6cd65d0db090` pelo runner self-hosted efêmero e
concluiu com sucesso: 47 testes portáveis e 10 de transporte/identidade. O
recibo e o link do run estão em `evidence/phase2/deployment/github-ci.json`; o
runner se desregistrou ao fim do job. A suíte local completa passou com 89
testes. Não foi verificada a data de expiração da trial nem o consumo de CU.
