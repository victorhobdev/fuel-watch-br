# Activator histórico — investigação da ausência de ação

O lote `ae5e0526-4c65-45bb-928c-f80ea4c9c7e1` chegou integralmente ao
Eventhouse: 1.020 payloads, 1.000 IDs únicos e classificações recalculadas.
O preview real do Activator mostrou também 1.020 eventos, com `alert_score`,
`benchmark_version` e `benchmark_status`. A hipótese de ausência desse campo
na origem foi refutada por essa observação.

Nenhum job apareceu no pipeline de auditoria e a consulta SQL não encontrou
linhas do lote. `get_activations_for_rule` retornou `DataNotAvailable`; esse erro
não equivale a um histórico vazio validado.

A inspeção da definição na interface mostrou Ocorrência sem seleção. Foi
salva a opção “Toda vez que a condição for atendida”, sem iniciar a regra.
A releitura REST mostrou `templateVersion: 1.3.1` e a linha
`OccurrenceOption`, `kind: EachTime`, `arguments: []`, ausente na definição
anterior. O gerador foi corrigido para reproduzir essa configuração.

Essa diferença é uma causa candidata concreta. A correção só será considerada
validada após observar a ação real. A sonda de dois eventos usa um ID separado
para preservar o lote original e aguarda a auditoria antes de solicitar a pausa.
Não foi executado manualmente o pipeline de auditoria para simular uma ação.
