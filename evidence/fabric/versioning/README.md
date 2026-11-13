# M03 — laboratório validado no Fabric

Experimento `ccbdb9dc-8c1a-487d-a034-1c8960edb67e`. Fonte: saída de console fornecida pelo usuário; bytes preservados em `console.jsonl`, resultado final em `summary.json` e 27 verificações locais em `validation.json`, dentro da pasta do experimento. O agente não consultou as tabelas remotamente nem reexecutou Spark.

Execução em 12/11/2026, 20:20:48–20:24:52, America/Sao_Paulo (timestamps originais UTC nos JSONs). Duração: 243,593442 segundos. Runtime informado: Spark 4.1.1.5.5.20260929.238183312 e Python 3.13.11. Manifesto igual ao pacote entregue.

Resultados reconciliados entre os 17 eventos e o resumo final:

- Sete publicações, uma repetição, oito rejeições e uma falha controlada antes da promoção.
- Correção de janeiro: exatamente uma atualização; chegada atrasada: uma inclusão; remoção revisada: uma exclusão.
- Duplicata exata e retry com hash correto: nenhum acréscimo ou alteração de negócio, apesar de publicarem outra versão de arquivo.
- Repetição, rejeições e falha controlada não geraram commit na tabela ativa. Sete publicações avançaram a versão ativa de 0 para 7, sem quebra de encadeamento.
- Falha antes da promoção preservou a versão 6; retry publicou a atualização na versão 7. O histórico manteve oito snapshots candidatos, incluindo o da falha.
- Quatro coletas finais; todas as comparações de negócio, seleção ativa, commit e escopo protegido retornaram verdadeiras.
- Silver oficial: versão 1 antes e depois, com comparação integral sem alteração informada pelo notebook.

Este aceite é do laboratório sintético serial. Não comprova republicação oficial da ANP, concorrência entre jobs, transação entre tabelas ou recuperação de perda do cluster. `official_integration_implemented=false` está explícito neste retorno histórico. A [seleção oficial/repetição do notebook 06](official/README.md) foi validada depois e fecha o M03 em conjunto com este laboratório.
