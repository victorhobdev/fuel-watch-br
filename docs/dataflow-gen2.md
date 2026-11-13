# M06 — referência municipal em Dataflow Gen2

Estado: **item Dataflow criado e definição relida no Fabric; refresh ainda não iniciado**. Não é uma nova referência canônica. A consulta SQL real confirmou 92 linhas e 92 códigos distintos em `lh_fuelwatch.dbo.ref_municipio_ibge`, no hash IBGE aprovado. [Preflight](../evidence/fabric/dataflow/reference-preflight-2026-11-13.json).

O exercício usa a própria referência preservada do M02, filtrada pelo hash, projeta código/nome/UF, aplica tipos textuais e remove espaços externos. O destino é somente `lab_m06_municipios`, no Lakehouse do laboratório. Não modifica `ref_municipio_ibge`, Silver ou Gold. Managed settings devem substituir a tabela em cada refresh; comprovar 92 linhas após a repetição continua obrigatório.

[mashup.pq](../fabric/m06/mashup.pq) inclui uma fixture inválida, identificada como sintética, que acrescenta uma linha e provoca `M06_REFERENCE_CONTRACT` antes de retornar o resultado. Ela é desativada por padrão. O aceite exige execução normal, repetição, erro real e recuperação; preparar o M não prova nenhum desses resultados.

## Dependências de conexão

A API inicialmente retornou apenas a conexão HTTP ANP existente. O conector Lakehouse está disponível e informa somente `OAuth2` como credencial suportada. O usuário criou `lh_fuelwatch_oauth` pelo fluxo interativo; a API confirmou Lakehouse/OAuth2. Nenhuma senha ou token foi copiado para a definição ou para o Git.

O item `df_m06_ibge_lab` foi criado pela API com o M e a conexão fornecida. O retorno `getDefinition` confirmou o M integral, o binding composto e `loadEnabled=false` no destino oculto. [Prova de autoria](../evidence/fabric/dataflow/authoring-2026-11-13.json). A [exportação nativa real](../fabric/m06/native/queryMetadata.json) mantém formato `202502` e remove bindings do ambiente; o template inicial fica separado. A origem tem load habilitado por padrão (o servidor omite `true` na releitura). Isso ainda não comprova resolução de credenciais em runtime ou implantação Git real.

## Verificação de execução

Após cada refresh, comparar os três campos nos dois sentidos com a projeção do snapshot canônico e verificar cardinalidade/unicidade, usando SQL no endpoint. Exigir zero diferenças inexplicadas, 92 linhas e tipos textuais. Guardar job_id, definição aplicada, erro esperado e resultado da recuperação. A fixture nunca deve alcançar dados oficiais.

Copy é o transporte preservado da ANP; notebook mantém validação/versionamento Spark; Dataflow pratica uma transformação Power Query pequena. Não encadear Copy e Dataflow para duplicar a ingestão oficial.

Referências: [definição Dataflow](https://learn.microsoft.com/en-us/rest/api/fabric/articles/item-management/definitions/dataflow-definition), [destinos e managed settings](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-data-destinations-and-managed-settings), [Create Connection](https://learn.microsoft.com/en-us/rest/api/fabric/core/connections/create-connection).
