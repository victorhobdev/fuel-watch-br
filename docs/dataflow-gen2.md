# M06 — referência municipal em Dataflow Gen2

Estado: **M06 CONCLUÍDO — 5/5 critérios aceitos no Fabric em 13/11/2026**. Quatro execuções reais e verificações SQL provaram carga, repetição, erro controlado e recuperação. A tabela de laboratório tem 92 linhas/códigos únicos e três campos varchar, sem diferenças na projeção canônica. [Aceite](../evidence/fabric/dataflow/m06-acceptance-2026-11-13.json).

| Caso | Job | Resultado |
|---|---|---|
| Inicial | `06fc923d-79ae-4670-9371-5380c194a45b` | Completed; 92 códigos e comparação integral |
| Repetição | `1b885fe0-512c-4b16-ae47-34ece03ed2b4` | Completed; 92 linhas, sem duplicação |
| Fixture inválida | `8bdaddc5-ed4e-4699-8e4b-a42b897c3df8` | Failed esperado; M06_REFERENCE_CONTRACT na query |
| Recuperação | `9fb44ee5-89bf-43e2-b4c3-620953b97b3b` | Completed; fixture false, referência e projeção iguais |

Os recibos estão em `evidence/fabric/dataflow/runs/`. A referência canônica permaneceu com o mesmo fingerprint nos quatro casos; a falha não foi apresentada como prova de preservação da tabela de laboratório antes da recuperação. Nenhuma tabela oficial foi destino de escrita.

O exercício usa a própria referência preservada do M02, filtrada pelo hash, projeta código/nome/UF, aplica tipos textuais e remove espaços externos. O destino é somente `lab_m06_municipios`, no Lakehouse do laboratório. Não modifica `ref_municipio_ibge`, Silver ou Gold. Managed settings devem substituir a tabela em cada refresh; comprovar 92 linhas após a repetição continua obrigatório.

[mashup.pq](../fabric/m06/mashup.pq) inclui uma fixture inválida, identificada como sintética, que acrescenta uma linha e provoca `M06_REFERENCE_CONTRACT` antes de retornar o resultado. O Fabric retornou `ModelBuilderEvaluationErrorCode` com a mensagem desse contrato na query `lab_m06_municipios`. A recuperação desativou a fixture, releu a definição e restaurou as 92 linhas verificadas.

## Dependências de conexão

A API inicialmente retornou apenas a conexão HTTP ANP existente. O conector Lakehouse está disponível e informa somente `OAuth2` como credencial suportada. O usuário criou `lh_fuelwatch_oauth` pelo fluxo interativo; a API confirmou Lakehouse/OAuth2. Nenhuma senha ou token foi copiado para a definição ou para o Git.

O item `df_m06_ibge_lab` foi criado pela API com o M e a conexão fornecida. O retorno `getDefinition` confirmou o M integral, o binding composto e `loadEnabled=false` no destino oculto. [Prova de autoria](../evidence/fabric/dataflow/authoring-2026-11-13.json). A [exportação nativa real](../fabric/m06/native/queryMetadata.json) mantém formato `202502` e remove bindings do ambiente; o template inicial fica separado. A origem tem load habilitado por padrão (o servidor omite `true` na releitura). A prova de autoria é complementada pelos quatro refreshes verificados; implantação Git real continua como M08.

Os refreshes posteriores comprovaram a conexão em runtime. O item é Dataflow Gen2 com suporte nativo a CI/CD/Git por padrão; a integração do workspace e a implantação efetiva continuam como M08. O endpoint usado foi `dataflows/{id}/jobs/execute/instances`, com `ApplyChangesIfNeeded`, delegado ao usuário; essa API específica está em preview e documenta ausência de suporte a service principal/managed identity. Não assumir que uma futura identidade CI possa executar esse job sem validar o suporte.

O serviço criou `StagingLakehouseForDataflows_20261113140901`, seu SQL endpoint e `StagingWarehouseForDataflows_20261113140901` no mesmo workspace. São dependências gerenciadas do Dataflow e permanecem na capacidade existente do trial. Registrá-las no inventário; não confundi-las com `lh_fuelwatch`/`wh_fuelwatch` nem removê-las enquanto o Dataflow depender delas.

## Verificação de execução

`tools/fabric/m06_job.py --start baseline|replay|invalid|recovery` aplica a definição quando muda a fixture e acompanha um único job. `--watch <id>` retoma a observação sem iniciar outro refresh. `check_m06.py <id> --same-as <verification.json>` compara todos os três campos, cardinalidade, unicidade e tipos no endpoint SQL. Os quatro resultados e a restauração da definição foram verificados; a exportação nativa final está com fixture false.

Copy é o transporte preservado da ANP; notebook mantém validação/versionamento Spark; Dataflow pratica uma transformação Power Query pequena. Não encadear Copy e Dataflow para duplicar a ingestão oficial.

Referências: [definição Dataflow](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/dataflow-definition), [destinos e managed settings](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-data-destinations-and-managed-settings), [CI/CD e Git](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-cicd-and-git-integration), [Execute API preview](https://learn.microsoft.com/en-us/rest/api/fabric/dataflow/background-jobs/run-on-demand-execute), [Create Connection](https://learn.microsoft.com/en-us/rest/api/fabric/core/connections/create-connection).
