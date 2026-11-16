# Operação histórica — cenários verificados no Fabric

O pipeline `pl_fuelwatch_historico` integra Copy binário, notebook 11,
notebook 12, verificação de visibilidade SQL e publicação transacional. O run
consumido pelo Warehouse vem da saída do notebook, sem selecionar o lote mais
recente por data. A biblioteca compartilhada usa caminho imutável por hash,
evitando conflito de arquivos entre as duas etapas na mesma sessão Spark.

| Cenário | Execução observada | Prova |
|---|---|---|
| Entrega nova no catálogo do projeto | Primeira ingestão dos quatro semestres históricos: 1.712.267 registros recebidos, 1.703.135 aceitos; publicação conjunta mantém 2026H1 | `evidence/phase2/history/silver-72918c9c-414e-40d0-8395-3ebdb0cb75d1.json` e `warehouse-first_joint_publish.json` |
| Repetição idêntica | Pipeline integrado `96898797-8ece-4393-a8ac-e59d9a3ac4c6`: reutiliza Silver, não executa candidata/publicação e mantém o registro publicado | `evidence/phase2/refresh/pipeline-96898797-8ece-4393-a8ac-e59d9a3ac4c6.json` |
| Correção de arquivo antigo | Laboratório `c3756c95-33c1-4c8c-9398-5544b0b78de7`: arquivo completo de 2024H1, um preço e quatro atributos corrigidos; candidata e Gold de 2.125.547 coletas, SCD2 com uma versão adicional | `evidence/phase2/history/lab/fabric-correction.json` |
| Interrupção antes do commit | Falha SQL injetada após as escritas; fingerprints completos de fato, dimensões, versões de origem e publicação permanecem iguais | `evidence/phase2/history/warehouse-fail_before_commit.json` |
| Recuperação | A mesma candidata aprovada é publicada com sucesso após a falha; comparação integral e preservação dos campos tipados de 2026H1 | `evidence/phase2/history/warehouse-recover_before_commit.json` |

“Entrega nova” é a primeira entrada desses arquivos no catálogo histórico do
projeto; não se afirma que a ANP os publicou agora. A correção é um experimento
**sintético**, em `lab_*`, com ZIP, versões Delta e Gold próprios. Não foi
inventada uma republicação oficial. O arquivo original e os dados oficiais
permaneceram iguais, conferidos por fingerprint integral antes/depois.

A execução integrada completa `010951d0-40c0-4e89-86de-20885cf7ed8b` teve todas
as etapas reconciliadas com o run publicado e os totais do Warehouse. Somente o
gate de leitura da visibilidade SQL pode repetir automaticamente. Publicação e
submissão de jobs não recebem retry cego após resultado incerto.

A descoberta em `scripts/discover_anp_versions.py --refresh` reconsulta o
catálogo e todos os semestres elegíveis, inclusive os antigos. A política em
`config/refresh-policy.json` identifica versões pelos bytes originais. Um novo
hash é preservado e exige perfil/contrato/referência aprovados antes de consumo;
data maior, ETag e Last-Modified não substituem o hash. Não se promete ausência
de tráfego HTTP para arquivos idênticos.

A agenda finita disparou o job `481d3ce1-a08c-4614-994e-d2362d8c9107` com
`invokeType=Scheduled`. O comportamento idêntico foi conferido; a agenda foi
desabilitada e relida pela API. Prova: `evidence/phase2/refresh/schedule-once.json`.
Nenhuma operação contínua foi habilitada.

O consumo analítico histórico, a comparação de postos comuns e a sincronização
final foram concluídos e reconciliados. O fechamento está em
`roadmap-fase2-cinco-marcos.md`; os artefatos de laboratório permanecem
identificados separadamente dos resultados oficiais.
