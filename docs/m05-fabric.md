# M05 — Pipeline mestre e recuperação

Estado: **M05 CONCLUÍDO — 5/5 critérios aceitos no Fabric em 13/11/2026**. O mestre nativo de 12 atividades executou carga normal, falhas Silver/Gold, recuperações, repetição e agendamento delimitado. As evidências foram conferidas por REST, OneLake e SQL; a agenda está desabilitada. M00–M04 permanecem aceitos, sem mudança dos snapshots aprovados.

| Prova | Job | Resultado |
|---|---|---|
| Carga completa | `3ceb55a5-8026-4950-97fb-c2eb229d6c1d` | Completed; lote e publicação correlacionados |
| Falha Silver | `b9812604-df3d-4705-bc30-5324be35779d` | Failed esperado; consumidores bloqueados, Gold intacta |
| Recuperação Silver | `5c9a3991-61b9-454a-a686-2a96c2c04c17` | Completed; negócio integral igual ao baseline |
| Falha Gold | `4145ce90-e750-4109-a0c7-4637ba50a209` | Failed esperado; rollback e guard aprovados |
| Recuperação Gold | `dc94cb54-4930-427f-9e08-6ea8b4996747` | Completed; negócio integral igual ao baseline |
| Repetição completa | `bc036008-ccea-404e-9362-ce9dc081db6b` | Completed; retry finito de importação no mesmo lote |
| Disparo agendado | `80575d95-2838-4b70-b9d4-1aad84ffb084` | Scheduled/Completed; agenda desabilitada |

[Bateria verificada](../evidence/fabric/orchestration/recovery-cases-2026-11-13.json), [agendamento](../evidence/fabric/orchestration/scheduled-run-2026-11-13.json), [recibos por job](../evidence/fabric/orchestration/pipeline-runs/3ceb55a5-8026-4950-97fb-c2eb229d6c1d/verification.json). Tentativas operacionais interrompidas foram preservadas separadamente, sem serem contadas como falhas Silver/Gold aprovadas. O resultado permanece 8.052 coletas, 502 postos, 27 municípios de cobertura, 518 versões observadas, 656 grupos semanais e soma de preços 52.777,200.

O [registro inicial de autoria pelo navegador](../evidence/fabric/orchestration/notebook08-ready.json) é histórico e não comprova a definição atual. A validação vigente usa leitura REST do código/metadados e as execuções correlacionadas acima.

## Contrato desta primeira integração

### Primeira execução completa — 13/11/2026

O job `3ceb55a5-8026-4950-97fb-c2eb229d6c1d` terminou `Completed` com `Capture_Baseline`, `Copy_ANP`, `Bronze`, `Silver`, `Export_Gold_Input`, `Import_Gold`, `Publish_Gold` e `Validate_Gold` em `Succeeded`. O lote publicado é `fc756f7e-a703-40b3-b8d5-c9d338679af8`; o registro Warehouse está `validated` e coincide com o recibo de exportação e o marcador publicado.

A conferência independente por API/OneLake/SQL passou: 422.418 linhas Bronze, 8.052 coletas Gold, 518 versões de posto, 656 grupos semanais, 181 datas, 92 municípios na referência dimensional e um produto. Os três estágios Spark retornaram o mesmo sessionId, com `created` no Bronze e `attached` nos seguintes. [Prova da tentativa e fingerprints](../evidence/fabric/orchestration/pipeline-runs/3ceb55a5-8026-4950-97fb-c2eb229d6c1d/verification.json).

Essa carga isoladamente fechou os dois primeiros critérios M05. Os ensaios posteriores de falha/recuperação/repetição foram serializados, preservaram interrupções operacionais e completaram os critérios restantes com o disparo agendado.

O recebimento continua HTTP/Binary da ANP, em caminho por `Pipeline RunId`. O hash aprovado e o escopo são parâmetros explícitos. Esta primeira integração aceita somente o snapshot já revisado; uma republicação diferente deve falhar no hash e passar pelo processo de revisão M03, nunca ser promovida automaticamente.

O notebook `08_pipeline_stage` é um wrapper parametrizado, sem dados embutidos. Ele referencia os notebooks 01, 06 e 07 por nome usando `notebookutils.notebook.run`, conserva os notebooks aceitos e exige recibo novo bem-sucedido de cada execução filha. Seus recibos ficam em `Files/audit/m05/<root_run_id>/<phase>/<attempt_id>.json`; o retorno de `notebookutils.notebook.exit` entrega o lote ao próximo estágio.

A definição atual foi restaurada pela API com rejeição do UUID zero, parâmetro raiz seguro e vínculo ao Lakehouse preservado. O antigo [preparation-status.json](../evidence/fabric/orchestration/preparation-status.json) é um checkpoint histórico, anterior a essa recuperação.

O pipeline usa atividades distintas para Copy, Bronze, Silver, exportação, importação Warehouse, publicação e validação, ligadas por sucesso. A referência IBGE preservada é consumida pelos notebooks; sua captura não é repetida implicitamente a cada execução.

A falha Silver é injetada no wrapper **após a validação do filho e antes de devolver sucesso**: comprova propagação de erro e bloqueio dos consumidores, sem afirmar rollback entre camadas. A falha Gold usa `gold.publish_gold @inject_fail_before_commit=1`, já disponível, para provocar erro após escritas dentro da transação. Ambas exigem comparar o estado publicado anterior, recuperar com falha desativada e repetir.

Limite operacional: laboratório serial, um publicador por vez. Ainda não há garantia de concorrência; a detecção de recibos novos bloqueia resultados ambíguos, mas não substitui exclusão mútua.

## Reprodução e verificação

- `python scripts/build_m05_notebook.py`: gera notebook com célula marcada `parameters` e corpo separado.
- `python -m unittest tests.test_m05_stage -v`: cinco testes locais com filhos simulados verificam propagação do caminho/hash, bloqueio sem retorno de sucesso, lote exato, nome real do recibo e rejeição de ausência/ambiguidade, inclusive com lote antigo disponível.
- Os testes locais não executam Spark, Copy ou SQL; as provas reais do aceite ficam nos recibos por job acima.
- `python scripts/build_m05_sql.py` prepara seis scripts, incluindo baseline imutável por tentativa, comparação das duas direções com cardinalidade e textos em bytes, importação do lote exato, publicação com falha opcional e validação correlacionada. Esses scripts foram executados no Warehouse, manualmente no componente inicial e pelo pipeline mestre nos ensaios completos.
- Suíte local atual: 70 testes de desenvolvimento e cinco testes do transporte no venv operacional aprovados. Os runtimes são separados. [Runbook executado](runbooks/recovery.md).

## Histórico de autoria — antes da validação runtime

O mestre foi configurado com 12 atividades e quatro parâmetros explícitos. O caminho é `Capture_Baseline → Copy_ANP → Bronze → Silver → Export_Gold_Input → Import_Gold → Publish_Gold → Validate_Gold`. Silver e Gold possuem caminhos de erro que primeiro verificam a proteção da publicação anterior e depois executam uma `Fail activity`, preservando o resultado de falha do pipeline.

Somente a importação tem três retries, com intervalo de 30 segundos, para tratar disponibilidade no endpoint SQL. Falhas injetadas não possuem retry automático. O lote vem de `Export_Gold_Input.output.result.exitValue`; esse caminho e a recepção dos parâmetros no notebook 08 foram confirmados pelos recibos e publicações reais.

A interface retornou **“Seu pipeline foi validado. Nenhum erro foi encontrado.”** A definição foi salva e relida pelo editor JSON; atividades e parâmetros coincidem semanticamente com o preparado. Essa validação é de autoria, não comprova execução. [Prova de autoria](../evidence/fabric/orchestration/pipeline-authoring-status.json).

As definições dos tipos Copy, TridentNotebook e Script vieram do próprio editor Fabric: [atividades-base](../fabric/m05/activity-baselines.json). O [export nativo salvo](../fabric/m05/pipeline.definition.redacted.json) troca bindings do ambiente por placeholders e remove identificação do editor. `scripts/build_m05_pipeline.py` prepara o template em `data/artifacts/m05/`, sem aplicar bindings nem executar serviços. Não é uma integração Git nativa de workspace; ela permanece M08.

## Componente SQL executado no Fabric — 13/11/2026

O Warehouse permaneceu disponível apesar do carregamento do editor de notebooks. Foram executados setup, captura de baseline, seis comparações de proteção, falha 51999 após escritas/antes do commit, nova comparação sem diferenças, recuperação em tentativa separada e reconciliação completa. Os recibos registram `gold_failed` e `validated`; o resultado preserva 8.052 coletas, 518 versões, 656 grupos semanais e soma 52.777,200 nas duas projeções.

Evidência histórica: [validation.json](../evidence/fabric/orchestration/sql-component-2026-11-13/validation.json). Esse exercício validava somente o componente SQL manual. O aceite de ponta a ponta veio posteriormente da bateria e do agendamento descritos no início deste documento.

A consulta auxiliar inicial usou `FOR JSON` em subconsulta e recebeu erro 15802 na linha 38. A execução corrigida posicionou `FOR JSON` no último operador e passou; o erro e o resultado foram preservados. Esse diagnóstico não exigiu alteração dos scripts Gold M04 nem das seis comparações de proteção.

## Dependências confirmadas

### Diagnóstico por API — 13/11/2026

O recibo real do exportador 07 é `audit/m04/<batch>/transfer.json`, enquanto o wrapper procurava `summary.json`. A tentativa `da5169bf-3a48-4deb-87c6-938180c62031` tinha um export bem-sucedido, lote `53e462be-7f74-41dd-a0e7-42a8c4682c5b`, e um wrapper com erro de descoberta. O problema era o contrato entre os notebooks; cache não foi comprovado como causa. A fixture local anterior usava o mesmo nome incorreto do wrapper, ocultando a falha. Corrigir a fixture primeiro reproduziu o erro; depois da correção, a suíte passou.

O wrapper agora recebe o nome explícito do recibo e consulta `notebookutils.fs` no caminho relativo `Files/`, preservando a exigência de exatamente um recibo novo. `summary.json` continua sendo o contrato do notebook 06. Nenhum recibo antigo é usado como fallback.

O backup REST também revelou célula remota truncada e sintaticamente inválida após a edição pelo navegador. A restauração usou `format=ipynb` explícito, preservou os metadados remotos e foi relida para comparar o código e a dependência do Lakehouse. O cliente trata a operação assíncrona pelo `Location` regional retornado pelo Fabric; HTTP 202 não é tratado como sucesso concluído. [Diagnóstico e recibos reais](../evidence/fabric/orchestration/api-recovery-2026-11-13/diagnosis.json).

O acesso direto passa por `tools/fabric/client.py` e `tools/fabric/m05_job.py`. `--start none|silver|gold` inicia uma tentativa; `--watch <job_id>` acompanha uma já iniciada, sem repetir o POST. Os bindings e saídas nativas ficam em `.local/`, ignorados pelo Git. Essa automação usa o trial existente, sem provisionar recursos pagos.

### Admissão Spark e compartilhamento de sessão

A nova tentativa `4821bccb-88c5-42fe-bc2a-eddc56247c03` passou em Copy/Bronze/Silver, mas a exportação recebeu HTTP 430 ao criar a sessão Livy, antes de executar o wrapper. O guard SQL comparou integralmente a publicação anterior e passou. Isso é uma falha operacional de admissão, distinta do erro anterior de nome do recibo. [Falha e guard](../evidence/fabric/orchestration/pipeline-runs/4821bccb-88c5-42fe-bc2a-eddc56247c03/capacity-failure.json).

A inspeção dos nove notebooks não encontrou sessões ativas esquecidas. As sessões Bronze/Silver constam como encerradas pelo sistema; a causa específica da contenção naquele instante não foi estabelecida. Portanto, não foi cancelado nenhum job presumidamente ocioso.

O workspace tinha `notebookPipelineRunEnabled=false` e cada atividade usou uma sessão diferente. Foi habilitado compartilhamento de sessão para pipelines, com a mesma `sessionTag=fuelwatch_m05_serial` nas três atividades. Pool, runtime e capacidade permaneceram iguais. A definição foi relida; o reaproveitamento foi depois confirmado por sessionIds iguais e `created/attached` nos recibos. Isso não é um benchmark controlado de desempenho M09. [Antes/depois](../evidence/fabric/orchestration/api-recovery-2026-11-13/session-sharing.json). Referência: [configuração de high concurrency em pipelines](https://learn.microsoft.com/en-us/fabric/data-engineering/configure-high-concurrency-session-notebooks-in-pipelines).

O workspace contém os notebooks 01/06/07, Lakehouse, endpoint SQL, Warehouse e pipeline `pl_anp_landing`. A interface do pipeline oferece `Exibir → Editar código JSON`; o recebimento atual foi lido por essa interface e preservado.

Referências oficiais consultadas: [Notebook activity e parâmetros](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity), [NotebookUtils: referência e retorno](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run), [Script activity e Warehouse](https://learn.microsoft.com/en-us/fabric/data-factory/script-activity). A configuração final foi relida pela API e o caminho real do retorno foi validado na execução.

A primeira tag usou hifens e foi rejeitada pelo servico com HTTP 400 antes de criar Spark (tentativa `2de93141-e32e-48f3-a859-1c87fc7e9deb`). O nome foi corrigido para letras/underscores, relido na definicao e coberto por teste de formato. O guard comprovou Gold intacta tambem nessa tentativa; isso nao conta como ensaio de falha Silver/Gold aprovado.

### Bibliotecas em uma sessão compartilhada

A tentativa `42f770b8-7c27-4cd7-94d6-3faeb593d1a5` comprovou o reaproveitamento: Bronze criou a sessão, Silver e export anexaram à mesma sessão. A exportação foi bloqueada por `addPyFile`: `fuelwatch_rules.zip` já estava registrado a partir de `m02_input`, e o bootstrap 07 tentava registrar o mesmo basename a partir de `m04_input`. O guard novamente confirmou a publicação anterior intacta. [Erro e sessionIds](../evidence/fabric/orchestration/pipeline-runs/42f770b8-7c27-4cd7-94d6-3faeb593d1a5/shared-library-collision.json).

Os dois ZIPs foram lidos diretamente do OneLake: ambos têm SHA-256 `2284a0d113a715125a9f79e5b99e7c1af7237f6afccfeac48531a47804119744`. O wrapper passa agora `p_rules_library_path` ao notebook 07 para usar o mesmo caminho já registrado. O bootstrap exclusivo de M04 exige que o arquivo esteja em Files e tenha o hash do pacote M04 aprovado; biblioteca diferente bloqueia a execução. O padrão standalone continua apontando para seu próprio bundle. Nenhum bundle preservado ou regra de negócio foi alterado. [Verificação das bibliotecas](../evidence/fabric/orchestration/api-recovery-2026-11-13/shared-library.json).

O notebook remoto 07 estava em uma célula concatenada; seu corpo de exportação foi comparado integralmente com o fonte local antes da atualização para células separadas e parâmetros marcados. Foram adicionados três testes de biblioteca: padrão standalone, alias idêntico e rejeição de bytes diferentes. Total: 65 testes locais aprovados; isso não substitui a validação do novo pipeline.
