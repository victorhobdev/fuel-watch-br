# Evidências Fabric do M02

O JSON `ibge/ebaf83ac-c2c2-46cc-b162-05187c469f64.json` foi fornecido pelo usuário após executar o notebook 03 no Fabric. O escape Markdown da URL foi removido; os demais valores foram preservados. O agente conferiu o retorno localmente, sem consultar a tabela remotamente.

Resultado: `ibge_reference_validated`, 92 municípios, nenhuma chave normalizada ambígua, hash do snapshot e hash do manifesto iguais aos aprovados no pacote local. A referência foi criada em `ref_municipio_ibge`; o caminho dos bytes originais preservados também consta da auditoria. O modo de origem é upload do snapshot oficial preservado, não uma nova chamada REST no Fabric.

Runtime observado nesse retorno: Spark `4.1.1.5.5.20260929.238183312`, Python `3.13.11`. Execução em 12/11/2026, 19:30:19–19:30:40 (America/Sao_Paulo); os timestamps originais são mantidos em UTC no JSON.

A Silver, o fixture distribuído e a repetição da Silver ainda não foram executados conforme as evidências recebidas. O próximo passo é parar a sessão 03 e executar o notebook 04 no mesmo Lakehouse padrão e com o mesmo bundle aprovado.
