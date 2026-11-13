# M10 — laboratorio sintetico separado

Estado: **aceito no Fabric**. O lote `daf2320c-b0bc-4eef-b908-a2dd80939088` teve 1.000 IDs e payloads reconciliados integralmente, vinte reinjeções contadas como duplicatas e dez eventos fora de ordem identificados. As quatro consultas KQL passaram. A transição sintética acima de 7,000 produziu uma ativação real e um job concluído no pipeline exclusivo de auditoria; a linha SQL corresponde ao lote. [Evidências](../evidence/fabric/streaming/).

A regra foi parada via MCP oficial do Activator e os dois destinos Eventstream estão `Paused`, com leitura posterior confirmada. O Custom endpoint permanece `Running` como endpoint passivo; o emissor finito terminou. O Eventhouse conserva `minimumConsumptionUnits=0`. Nenhuma notificação externa foi habilitada. O texto abaixo descreve o desenho e os critérios usados; sua execução aceita está nos recibos, não apenas nas definições.

O gerador produz 1.000 IDs UUID unicos/reproduziveis dentro de um `lab_run_id`, dez postos `SYNTHETIC_001`–`010`, GASOLINA/BRL/litro e `is_synthetic=true`. Nenhum registro vem da ANP ou representa preco real. `event_time` UTC fica no passado; dez eventos marcados chegam fora da ordem temporal. A emissao finita sera registrada separadamente, sem confundir preparo do arquivo com confirmacao do transporte ou da ingestao.

O lote tem dez eventos iniciais de seed para conferir schema/transporte e mais 989 de baseline, todos a 6,100; um evento final do posto sintetico 010 a 7,500; vinte reinjecoes exatas dos primeiros IDs. O limiar do teste Activator e 7,000. So enviar a transicao depois de conferir baseline/ativacao da regra; uma definicao aceita nao comprova regra em funcionamento. Deduplicar por `(lab_run_id,event_id)` sem prometer exactly-once no transporte.

Topologia proposta: Custom endpoint → Eventstream `es_fuelwatch_lab` → Eventhouse `eh_fuelwatch_lab`/KQL database `kql_fuelwatch_lab`. Todos separados das tabelas oficiais. Usar somente a capacidade trial existente, sem Always-On/minimum consumption contratado. Conexao SAS/endpoints reais ficam em `.local`, nunca no Git ou chat. Nao criar Azure Event Hubs pago para imitar o endpoint gerenciado do Eventstream.

Quatro consultas de aceite: ultimo preco por posto/produto com `arg_max(event_time,...)`; janela por `bin(event_time,5m)` sobre IDs deduplicados; cobertura/igualdade de conjuntos; duplicatas e atraso com `ingestion_time()` separado de `event_time`. O manifesto de origem preserva IDs e payloads; comparar IDs reais recebidos, nao so `dcount()` aproximado.

Para a acao controlada do Activator, preferir um pipeline exclusivo que grava auditoria sintetica no projeto. Esse e um destino interno proposto, sem envio de email/Teams. Uma notificacao externa exige definir canal/destinatario e autorizacao antes de habilita-la. O pipeline mestre ANP nao e o alvo do alerta. Registrar rule enabled/readback, transicao e job/registro de auditoria realmente observado; desligar regra/emissor ao fim.

O Eventhouse deve usar `minimumConsumptionUnits=0` e nenhuma alteracao de SKU. A aceitacao do laboratorio depende de reconciliar 1.000 IDs, contabilizar vinte duplicatas e eventos atrasados, verificar quatro consultas e observar o disparo real. Codigo local e testes do gerador nao fecham M10.

Referencias: [Eventstream APIs](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/eventstream-rest-api), [custom endpoint](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/add-source-custom-app), [Activator definition](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/reflex-definition), [Activator REST/action](https://learn.microsoft.com/en-us/fabric/real-time-hub/consume-events-activator-rest-api).
