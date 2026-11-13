# M09 — protocolo de desempenho

Estado: **seis medições executadas no Fabric e reconciliadas por SQL em 13/11/2026**. Ainda será preciso repetir as verificações pertinentes no destino após M08.

O experimento `weekly_shuffle_200_vs_8_v1` testa a agregação semanal da fatia já aceita. Para somente 8.052 coletas, 200 partições de shuffle podem acrescentar trabalho desnecessário; comparar 8 é uma hipótese delimitada, não uma recomendação global. AQE permanece com a configuração observada, igual nas duas fases; pode coalescer ambas e eliminar um possível ganho.

Fixar Silver `silver_preco_publicado` Delta version 0, snapshot aprovado `3da66482-2dad-489f-8450-b7ded2005f3d`, ANP SHA `a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c`, IBGE SHA `2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0` e escopo `anp-2026-1-rj-gasolina`. Validar tipos, metadados, 8.052 linhas/502 CNPJs/27 municípios antes de medir.

Usar **uma sessão Spark**, mesmo pool/runtime/capacidade, sem outra execução do projeto ativa. Não executar pipeline/Dataflow ao mesmo tempo. Registrar sessão, versões Spark/Python, conf AQE/shuffle, arquivos/bytes da entrada e plano físico. A capacidade trial é compartilhada e não isolada de toda variação de plataforma.

Materializar a mesma entrada em cache uma vez. Para cada fase, fazer um aquecimento excluído e três medições de `collect()` do mesmo agrupamento: contagem de coletas, postos distintos, soma, mínimo/máximo e sinais incomuns por semana/município/produto/moeda/unidade. Construção da expressão, captura do plano e serialização das evidências ficam fora do tempo medido. Não cachear o resultado agregado. Baseline usa shuffle=200; intervenção muda **somente** shuffle=8. Fixar a ordem baseline → intervenção; registrar que aquecimento residual e ordem limitam a inferência causal com n=3.

Comparar todas as 13 colunas e 656 grupos em cada medição; confrontar também com Gold por T-SQL no verificador externo. Registrar mediana e variação, duração de carregamento/cache separada e tarefas/jobs quando disponíveis. O tempo da sessão/job inclui inicialização e não é o tempo da consulta. Custo/CU não disponível deve ser `não medido`, nunca estimado a partir de segundos de notebook.

Ao terminar ou falhar, restaurar shuffle anterior e liberar somente o DataFrame cacheado por este notebook. Verificar que a versão Delta atual não mudou. Não aplicar OPTIMIZE, VACUUM, reparticionamento persistente ou alteração de pool. Não promover a configuração para produção automaticamente: ganho nulo/regressão é resultado válido. Nova implantação M08 exige repetir as verificações operacionais pertinentes no destino.

Referências: [Spark tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html), [concorrência Spark no Fabric](https://learn.microsoft.com/en-us/fabric/data-engineering/spark-job-concurrency-and-queueing).

## Resultado observado

Job `e2ac7876-631a-4f46-aef9-b7814500d57a`, experimento `b8c3587a-73a8-4a97-9e5e-f0e1261bbdac`. [Medições e reconciliação](../evidence/fabric/performance/b8c3587a-73a8-4a97-9e5e-f0e1261bbdac/verification.json), [receipt completo](../evidence/fabric/performance/b8c3587a-73a8-4a97-9e5e-f0e1261bbdac/summary.json).

| Fase | Tempos medidos (s) | Mediana (s) | Tarefas por amostra |
|---|---|---|---|
| Baseline, shuffle 200 | 0,5170; 0,6887; 0,5062 | 0,5170 | 27 |
| Intervenção, shuffle 8 | 0,3190; 0,2444; 0,2408 | 0,2444 | 27 |

A diferença entre medianas foi **−52,72% neste experimento**, com cache quente e uma única sessão. Os aquecimentos excluídos foram 1,4641 s e 0,2951 s; o carregamento/materialização do cache levou 1,9057 s. AQE e coalescing estavam habilitados. O número observado de tarefas foi igual nas fases: a diferença de tempo não demonstra que houve menos tarefas, nem identifica sozinha a causa de toda a variação.

Foram lidos metadados de **200 arquivos, 4.938.022 bytes**, para 8.052 coletas. O agregado manteve 656 grupos e coincidiu integralmente com as 13 colunas do Gold em todas as amostras. A consulta Gold de conferência levou 0,7998 s em uma observação; não é um benchmark SQL de três repetições. O pipeline agendado de referência levou cerca de 391,6 s e transportou ZIP de 8.488.624 bytes/422.418 registros; ele não foi comparado antes/depois desta intervenção.

**Decisão:** preservar a configuração produtiva original. Shuffle 8 fica como alternativa do experimento; repetir em ordem alternada e medir leitura fim a fim seria necessário antes de promover uma otimização global. Os 200 arquivos sugerem uma investigação futura sobre arquivos pequenos, mas este ensaio em cache não mede compactação. Não aplicar OPTIMIZE/VACUUM por inferência de ganho.

O verificador confirmou restauração de shuffle 200 e versão Delta inalterada; nenhum dado oficial foi escrito. Não foram medidos CU nem custo. Planos físicos são preservados com hashes originais; a cópia versionada deve retirar IDs/endereços de ambiente e identificar a redação.

A primeira tentativa `949da8d4-6da6-49aa-a799-abbd979526a3` foi rejeitada antes do código por ausência de `metadata.language_info.name`. Corrigido para `python` e relido antes de uma nova tentativa. Um erro de conversão ao pedir definição no formato padrão foi resolvido lendo explicitamente `getDefinition?format=ipynb`; o código publicado já estava íntegro. O verificador usa a janela do job retornada pelo serviço: a execução pode iniciar antes de o cliente receber o HTTP 202.
