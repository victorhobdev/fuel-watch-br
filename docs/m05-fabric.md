# M05 — Pipeline mestre e recuperação

Estado: **em desenvolvimento; nenhuma execução do pipeline mestre validada ainda**. M00–M04 permanecem aceitos; o checkpoint M04 é `86f0969`. A cópia nativa `pl_fuelwatch_master` e o notebook 08 foram criados no trial. A descoberta dos parâmetros ainda não foi confirmada; posteriormente o editor de notebooks permaneceu carregando, inclusive após reload e abertura em nova guia. A lista do workspace funciona e mostra os dois itens. Não executar o mestre até conferir a marcação da célula e completar as dependências e atividades SQL.

## Contrato desta primeira integração

O recebimento continua HTTP/Binary da ANP, em caminho por `Pipeline RunId`. O hash aprovado e o escopo são parâmetros explícitos. Esta primeira integração aceita somente o snapshot já revisado; uma republicação diferente deve falhar no hash e passar pelo processo de revisão M03, nunca ser promovida automaticamente.

O notebook `08_pipeline_stage` é um wrapper parametrizado, sem dados embutidos. Ele referencia os notebooks 01, 06 e 07 por nome usando `notebookutils.notebook.run`, conserva os notebooks aceitos e exige recibo novo bem-sucedido de cada execução filha. Seus recibos ficam em `Files/audit/m05/<root_run_id>/<phase>/<attempt_id>.json`; o retorno de `notebookutils.notebook.exit` entrega o lote ao próximo estágio.

Antes da retomada, reaplicar a versão local atual do notebook 08: ela acrescenta rejeição do UUID zero quando o parâmetro raiz não chega. A versão inicialmente colada no serviço foi comparada integralmente, mas essa proteção posterior ainda não foi aplicada por causa do carregamento do editor. Estado observado: [preparation-status.json](../evidence/fabric/orchestration/preparation-status.json).

O pipeline deve ter atividades distintas para Copy, Bronze, Silver, exportação, importação Warehouse, publicação e validação, ligadas por sucesso. A referência IBGE preservada é consumida pelos notebooks; sua captura não é repetida implicitamente a cada execução.

A falha Silver é injetada no wrapper **após a validação do filho e antes de devolver sucesso**: comprova propagação de erro e bloqueio dos consumidores, sem afirmar rollback entre camadas. A falha Gold usa `gold.publish_gold @inject_fail_before_commit=1`, já disponível, para provocar erro após escritas dentro da transação. Ambas exigem comparar o estado publicado anterior, recuperar com falha desativada e repetir.

Limite operacional: laboratório serial, um publicador por vez. Ainda não há garantia de concorrência; a detecção de recibos novos bloqueia resultados ambíguos, mas não substitui exclusão mútua.

## Verificação preparada

- `python scripts/build_m05_notebook.py`: gera notebook com célula marcada `parameters` e corpo separado.
- `python -m unittest tests.test_m05_stage -v`: quatro testes locais com filhos simulados verificam propagação do caminho/hash, bloqueio sem retorno de sucesso, lote exato e falha/ausência de recibo.
- Os testes não executam Spark, Copy ou SQL. O aceite depende de execuções reais no Fabric.
- `python scripts/build_m05_sql.py` prepara seis scripts, incluindo baseline imutável por tentativa, comparação das duas direções com cardinalidade e textos em bytes, importação do lote exato, publicação com falha opcional e validação correlacionada. O dialeto ainda não foi executado no Warehouse.
- Suíte local atual: 57 testes aprovados. [Runbook preparado](runbooks/recovery.md).

## Dependências confirmadas

O workspace contém os notebooks 01/06/07, Lakehouse, endpoint SQL, Warehouse e pipeline `pl_anp_landing`. A interface do pipeline oferece `Exibir → Editar código JSON`; o recebimento atual foi lido por essa interface e preservado.

Referências oficiais consultadas: [Notebook activity e parâmetros](https://learn.microsoft.com/en-us/fabric/data-factory/notebook-activity), [NotebookUtils: referência e retorno](https://learn.microsoft.com/en-us/fabric/data-engineering/notebookutils/notebookutils-notebook-run), [Script activity e Warehouse](https://learn.microsoft.com/en-us/fabric/data-factory/script-activity). A configuração final e o caminho real do retorno serão confirmados na execução.
