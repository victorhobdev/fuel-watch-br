# M09 — operação e diagnóstico

Estado: **em execução**, aceite ainda aberto. A [visão operacional](../evidence/fabric/operations/execution-index-2026-11-13.json) relaciona sete execuções funcionais M05 verificadas com origem/hash, runs Bronze/Silver, contagens/rejeições, lote Gold, estados, duração das atividades e publicação. `null` significa não registrado/não produzido, nunca zero implícito. A geração do índice é local; os registros de origem são execuções reais do Fabric já conferidas.

Para localizar uma carga completa, usar `80575d95-2838-4b70-b9d4-1aad84ffb084` (`invokeType=Scheduled`). Para uma falha Silver usar `b9812604-df3d-4705-bc30-5324be35779d`; para rollback após INSERT Gold, `4145ce90-e750-4109-a0c7-4637ba50a209`. A evidência de cada run contém atividades/receipts e fingerprints. As falhas esperadas não foram apagadas ou renomeadas como sucesso: a verificação funcional é que passou.

## Ambiente observado

O inventário por API encontrou capacidade **FTL4 Active, Brazil South**, workspace dev nessa capacidade, Starter Pool, runtime configurado **2.0**, máximo 10 nós/9 executores e timeout de sessão 20 minutos. O Spark real observado no M05 foi `4.1.1.5.5.20260929.238183312`, Python 3.13.11. Os limites de pool configurados não provam nós/executores efetivamente alocados em cada instante. Não há data exata de expiração do trial verificada; não inferir vencimento a partir do nome da capacidade.

Dataflow Gen2 criou seu staging Warehouse/Lakehouse; são dependências gerenciadas do serviço. Não removê-las sem avaliar a dependência. O inventário público retira IDs e nomes de contas; bindings reais ficam em `.local`.

## Incidentes reproduzíveis

1. **Receipt errado no export:** o wrapper buscava `summary.json`, mas o notebook 07 escreve `transfer.json`. A atividade filha havia terminado; o wrapper falhava ao procurar o resultado. Corrigido o contrato de nome e a seleção exata de um receipt novo. Cache não foi comprovado como causa.
2. **Admissão Spark HTTP 430:** houve rejeição antes da execução do export e nova rejeição numa recuperação imediata. O inventário posterior não encontrou sessões ativas, portanto não identifica retrospectivamente todos os consumidores da capacidade no instante da rejeição. O erro comprova rejeição de admissão, não permite atribuir toda a causa a um notebook desconhecido. Não comprar SKU como primeira resposta.
3. **Compartilhamento e biblioteca:** pipeline passou a reutilizar uma sessão com High concurrency e `sessionTag=fuelwatch_m05_serial`. Hífens no tag produziram 400 e foram removidos. A mesma sessão revelou ZIPs de mesmo basename em dois caminhos; leitura OneLake comprovou bytes idênticos e o export passou a reutilizar o caminho canônico somente após verificar SHA aprovado. Runs posteriores mostram o fluxo completo sem a colisão. Isso demonstra a correção local e a reutilização, não isolamento permanente da capacidade.
4. **Job terminal antes de liberar sessão:** o iniciador consulta Livy e espera término mais 60 s antes de outro pipeline. Não cancela sessões automaticamente e recusa iniciar se a condição persistir. Verificar `Monitoring hub` e `Workspace settings → Job management` quando precisar de inspeção interativa.
5. **Monitoramento interrompido por rede:** retomar o mesmo ID com `--watch`. Não repetir POST de início automaticamente. O cliente repete somente leituras idempotentes e mantém o histórico das interrupções.
6. **SQL endpoint ainda sem manifesto:** no replay completo, Import_Gold teve uma falha e um sucesso com o mesmo lote/comando, separados por 31,278544 s. Retry configurado é finito (3, intervalo 30 s). Não há número nativo `retryAttempt` retornado; os dois activity runs são a prova observada.

## Recuperação e encerramento

- Antes de iniciar, conferir jobs/sessões e agendas. Um terminal de CLI fechado não significa job cancelado. `--watch` acompanha a mesma tentativa; um novo POST é uma nova execução.
- Guardar o ID aceito imediatamente. Se o POST perder a resposta, inspecionar histórico antes de tentar novamente. Não transformar timeout de observação em autorização para duplicar carga.
- Falha Silver impede export/import/publicação. Corrigir entrada/contrato e executar nova tentativa, preservando origem imutável e publicação anterior.
- Falha Gold deve registrar `gold_failed` e proteger a publicação anterior. Confrontar guards com o baseline da própria tentativa; um baseline antigo comparado após uma publicação legítima pode acusar diferença esperada.
- Os comandos e verificadores reais estão em `tools/fabric/README.md`; M05 agendas estão desabilitadas e M06 fixture inválida foi restaurada para false.
- Reter raw/manifestos/receipts e snapshots utilizados por recuperação/time travel. Este projeto não tem política de descarte implementada; não rodar VACUUM para liberar espaço sem primeiro definir retenção e testar restauração. OPTIMIZE, V-Order e particionamento persistente não foram aplicados por este experimento.
- Medir consumo por métricas da capacidade quando disponíveis; duração de notebook não é CU nem valor monetário. Não habilitar recurso pago ou consumir crédito Azure sem custo apresentado e autorização.
- Ao encerrar, parar somente sessões/labs do projeto, desligar emissores/agendas/runner temporários e verificar por leitura. Não apagar staging gerenciado ou dados aceitos como atalho de limpeza.

O [protocolo de desempenho](performance.md) separa seis medições controladas do histórico funcional. Depois de M08, repetir inventário e verificações relevantes no workspace de teste; os resultados de dev não provam o comportamento do destino.

Referências: [Spark admission/queueing](https://learn.microsoft.com/en-us/fabric/data-engineering/spark-job-concurrency-and-queueing), [Spark tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html).


## Recuperação observada após implantação

No teste M08, a tentativa `96bd92e8-66a0-42e0-b047-1d397d54fded` esgotou quatro tentativas de Import_Gold porque o manifesto ainda não estava visível no SQL endpoint. A consulta posterior confirmou exatamente um manifesto do lote `6535cf07-75de-47cc-bc3b-1c5e0153f0d3`, sem duplicação; Gold ainda apontava a publicação anterior.

A recuperação conferiu `90_assert_unchanged.sql` para a tentativa, importou o comando resolvido da própria atividade com esse mesmo batch, publicou e validou. Não escolheu o lote mais recente nem refez Spark. As seis projeções de negócio ficaram iguais à execução completa de referência. A tentativa de pipeline permanece Failed; [o recibo separado](../evidence/fabric/deployment/audit-recovery.json) comprova a recuperação CLI. O prazo de sincronização não foi inferido como SLA; retries finitos protegem contra espera infinita.


Inventário final de 13/11: [dev/test sem jobs, sessões Spark ou agendas de pipeline ativos](../evidence/fabric/operations/resource-audit-2026-11-13.json). [MCP confirmou regra parada e destinos pausados](../evidence/fabric/streaming/daf2320c-b0bc-4eef-b908-a2dd80939088/mcp-shutdown-verification.json). O Custom endpoint permanece passivo Running; não foi declarado pausado. Os itens e evidências foram preservados. A capacidade trial continua ativa, sem vencimento nem consumo de CU verificados.
