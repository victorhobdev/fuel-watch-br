# M05 — evidência parcial

`preparation-status.json` é o registro histórico da preparação. `notebook08-prepared.jpg` mostra o notebook criado; não prova parâmetros ou execução. O usuário confirmou que o editor também fica carregando em sua sessão.

Em `sql-component-2026-11-13/` está a execução real do componente Warehouse, conduzida pelo agente na interface autorizada:

- Setup e baseline capturados; seis guards verificam fatos em bytes, versões de posto, publicação com timestamp, calendário, municípios e produto. Cada guard compara contagem e diferenças nas duas direções.
- Tentativa `9b58a7fd-f29a-4d26-b807-e1045f95528a`: erro esperado 51999 após escritas e antes do commit; o guard seguinte passou sem diferenças, inclusive no marcador anterior.
- Recuperação `fe96f77b-d853-4ab7-8433-325a8ce73ccf`: publicação com falha desativada, reconciliação completa M04 e recibo `validated`.
- A consulta final encontrou 8.052 fatos, 518 versões e 656 grupos semanais; soma dos preços 52.777,200 na fato e no semanal. As identidades e todos os campos da validação M04 coincidem com o aceite anterior, exceto horário da checagem.
- O JSON de validação consolida oito verificações verdadeiras; `10-attempt-ledger.json` contém os dois recibos reais. `recovery-ledger.jpg` e `after-fault-protected.jpg` preservam a interface.

Limites: execução manual no Warehouse, reutilizando o lote M04 já aprovado. Não executamos o pipeline mestre, Copy, Spark ou agendamento nesse experimento. O status do script foi nomeado `m05_gold_attempt_validated` para não sugerir que a execução SQL isolada comprove o pipeline completo. M05 continua parcial e o projeto permanece com 5/12 marcos aceitos.

O erro SQL 15802 em `02-before-guard.txt` veio de uma consulta auxiliar com `FOR JSON` em subconsulta. A linha 38 corresponde a essa consulta; as 36 linhas do guard foram mantidas. A versão corrigida usa `FOR JSON` no nível externo, conforme [T-SQL surface area](https://learn.microsoft.com/en-us/fabric/data-warehouse/tsql-surface-area), e consta em `03-before-guard-validated.txt`.

## Autoria nativa do pipeline

`pipeline-authoring-status.json` e `pipeline-authoring-validated.jpg` registram a validação de autoria sem erros. O mestre tem 12 atividades, dependências de sucesso no caminho oficial e tratamento de falhas com guard seguido de `Fail`. A definição foi salva, relida e comparada semanticamente; apenas a ordem das propriedades JSON foi normalizada pelo Fabric. `pipeline-master-saved.jpg` mostra o grafo salvo.

O export real está em `fabric/m05/pipeline.definition.redacted.json`, com bindings substituídos e sem identificação pessoal do editor. Não contém o destino concreto do ambiente. Não houve execução do mestre, portanto esses arquivos não fecham critérios M05 nem comprovam Git/implantação M08.
