# M05 — Pipeline mestre e recuperação

Estado: **em desenvolvimento; nenhuma execução completa do pipeline mestre validada ainda**. M00–M04 permanecem aceitos; o checkpoint M04 é `86f0969`. O mestre nativo tem 12 atividades. A primeira execução real completou Copy, Bronze e Silver, mas falhou na descoberta do recibo da exportação, antes de importar/publicar Gold. A recuperação do notebook 08 por REST foi conferida por leitura independente; uma nova tentativa sem falha injetada está em acompanhamento.

Atualização de 13/11: o editor voltou a abrir nos notebooks 06 e 08, sem causa confirmada para o carregamento anterior. A versão local do wrapper foi aplicada e comparada integralmente pelo comando de copiar a célula; a proteção do UUID zero e o badge `Parameters` foram conferidos, com confirmação de salvamento. [Prova do wrapper](../evidence/fabric/orchestration/notebook08-ready.json). A validação runtime ainda depende do resultado do pipeline.

## Contrato desta primeira integração

O recebimento continua HTTP/Binary da ANP, em caminho por `Pipeline RunId`. O hash aprovado e o escopo são parâmetros explícitos. Esta primeira integração aceita somente o snapshot já revisado; uma republicação diferente deve falhar no hash e passar pelo processo de revisão M03, nunca ser promovida automaticamente.

O notebook `08_pipeline_stage` é um wrapper parametrizado, sem dados embutidos. Ele referencia os notebooks 01, 06 e 07 por nome usando `notebookutils.notebook.run`, conserva os notebooks aceitos e exige recibo novo bem-sucedido de cada execução filha. Seus recibos ficam em `Files/audit/m05/<root_run_id>/<phase>/<attempt_id>.json`; o retorno de `notebookutils.notebook.exit` entrega o lote ao próximo estágio.

A definição atual foi restaurada pela API com rejeição do UUID zero, parâmetro raiz seguro e vínculo ao Lakehouse preservado. O antigo [preparation-status.json](../evidence/fabric/orchestration/preparation-status.json) é um checkpoint histórico, anterior a essa recuperação.

O pipeline deve ter atividades distintas para Copy, Bronze, Silver, exportação, importação Warehouse, publicação e validação, ligadas por sucesso. A referência IBGE preservada é consumida pelos notebooks; sua captura não é repetida implicitamente a cada execução.

A falha Silver é injetada no wrapper **após a validação do filho e antes de devolver sucesso**: comprova propagação de erro e bloqueio dos consumidores, sem afirmar rollback entre camadas. A falha Gold usa `gold.publish_gold @inject_fail_before_commit=1`, já disponível, para provocar erro após escritas dentro da transação. Ambas exigem comparar o estado publicado anterior, recuperar com falha desativada e repetir.

Limite operacional: laboratório serial, um publicador por vez. Ainda não há garantia de concorrência; a detecção de recibos novos bloqueia resultados ambíguos, mas não substitui exclusão mútua.

## Verificação preparada

- `python scripts/build_m05_notebook.py`: gera notebook com célula marcada `parameters` e corpo separado.
- `python -m unittest tests.test_m05_stage -v`: cinco testes locais com filhos simulados verificam propagação do caminho/hash, bloqueio sem retorno de sucesso, lote exato, nome real do recibo e rejeição de ausência/ambiguidade, inclusive com lote antigo disponível.
- Os testes não executam Spark, Copy ou SQL. O aceite depende de execuções reais no Fabric.
- `python scripts/build_m05_sql.py` prepara seis scripts, incluindo baseline imutável por tentativa, comparação das duas direções com cardinalidade e textos em bytes, importação do lote exato, publicação com falha opcional e validação correlacionada. O dialeto ainda não foi executado no Warehouse.
- Suíte local atual: 62 testes aprovados com o Python de desenvolvimento; o venv operacional não contém pyarrow/nbformat e não é o runtime dessa suíte. [Runbook preparado](runbooks/recovery.md).

## Pipeline nativo salvo — execução ainda pendente

O mestre foi configurado com 12 atividades e quatro parâmetros explícitos. O caminho é `Capture_Baseline → Copy_ANP → Bronze → Silver → Export_Gold_Input → Import_Gold → Publish_Gold → Validate_Gold`. Silver e Gold possuem caminhos de erro que primeiro verificam a proteção da publicação anterior e depois executam uma `Fail activity`, preservando o resultado de falha do pipeline.

Somente a importação tem três retries, com intervalo de 30 segundos, para sincronização do endpoint SQL. Falhas injetadas não possuem retry automático. O lote vem de `Export_Gold_Input.output.result.exitValue`; esse caminho de retorno ainda exige confirmação em runtime, assim como a recepção dos parâmetros no notebook 08.

A interface retornou **“Seu pipeline foi validado. Nenhum erro foi encontrado.”** A definição foi salva e relida pelo editor JSON; atividades e parâmetros coincidem semanticamente com o preparado. Essa validação é de autoria, não comprova execução. [Prova de autoria](../evidence/fabric/orchestration/pipeline-authoring-status.json).

As definições dos tipos Copy, TridentNotebook e Script vieram do próprio editor Fabric: [atividades-base](../fabric/m05/activity-baselines.json). O [export nativo salvo](../fabric/m05/pipeline.definition.redacted.json) troca bindings do ambiente por placeholders e remove identificação do editor. `scripts/build_m05_pipeline.py` prepara o template em `data/artifacts/m05/`, sem aplicar bindings nem executar serviços. Não é uma integração Git nativa de workspace; ela permanece M08.

## Componente SQL executado no Fabric — 13/11/2026

O Warehouse permaneceu disponível apesar do carregamento do editor de notebooks. Foram executados setup, captura de baseline, seis comparações de proteção, falha 51999 após escritas/antes do commit, nova comparação sem diferenças, recuperação em tentativa separada e reconciliação completa. Os recibos registram `gold_failed` e `validated`; o resultado preserva 8.052 coletas, 518 versões, 656 grupos semanais e soma 52.777,200 nas duas projeções.

Evidência: [validation.json](../evidence/fabric/orchestration/sql-component-2026-11-13/validation.json). Isso valida **somente o componente SQL por execução manual na interface**. Copy, Spark, propagação dos parâmetros, dependências do pipeline mestre, falha Silver e agendamento continuam pendentes. Nenhum critério de ponta a ponta M05 foi marcado como completo.

A consulta auxiliar inicial usou `FOR JSON` em subconsulta e recebeu erro 15802 na linha 38. A execução corrigida posicionou `FOR JSON` no último operador e passou; o erro e o resultado foram preservados. Esse diagnóstico não exigiu alteração dos scripts Gold M04 nem das seis comparações de proteção.

## Dependências confirmadas

### Diagnóstico por API — 13/11/2026

O recibo real do exportador 07 é `audit/m04/<batch>/transfer.json`, enquanto o wrapper procurava `summary.json`. A tentativa `da5169bf-3a48-4deb-87c6-938180c62031` tinha um export bem-sucedido, lote `53e462be-7f74-41dd-a0e7-42a8c4682c5b`, e um wrapper com erro de descoberta. O problema era o contrato entre os notebooks; cache não foi comprovado como causa. A fixture local anterior usava o mesmo nome incorreto do wrapper, ocultando a falha. Corrigir a fixture primeiro reproduziu o erro; depois da correção, a suíte passou.

O wrapper agora recebe o nome explícito do recibo e consulta `notebookutils.fs` no caminho relativo `Files/`, preservando a exigência de exatamente um recibo novo. `summary.json` continua sendo o contrato do notebook 06. Nenhum recibo antigo é usado como fallback.

O backup REST também revelou célula remota truncada e sintaticamente inválida após a edição pelo navegador. A restauração usou `format=ipynb` explícito, preservou os metadados remotos e foi relida para comparar o código e a dependência do Lakehouse. O cliente trata a operação assíncrona pelo `Location` regional retornado pelo Fabric; HTTP 202 não é tratado como sucesso concluído. [Diagnóstico e recibos reais](../evidence/fabric/orchestration/api-recovery-2026-11-13/diagnosis.json).

O acesso direto passa por `tools/fabric/client.py` e `tools/fabric/m05_job.py`. `--start none|silver|gold` inicia uma tentativa; `--watch <job_id>` acompanha uma já iniciada, sem repetir o POST. Os bindings e saídas nativas ficam em `.local/`, ignorados pelo Git. Essa automação usa o trial existente, sem provisionar recursos pagos.

O workspace contém os notebooks 01/06/07, Lakehouse, endpoint SQL, Warehouse e pipeline `pl_anp_landing`. A interface do pipeline oferece `Exibir → Editar código JSON`; o recebimento atual foi lido por essa interface e preservado.

Referências oficiais consultadas: [Notebook activity e parâmetros](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity), [NotebookUtils: referência e retorno](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run), [Script activity e Warehouse](https://learn.microsoft.com/en-us/fabric/data-factory/script-activity). A configuração final e o caminho real do retorno serão confirmados na execução.
