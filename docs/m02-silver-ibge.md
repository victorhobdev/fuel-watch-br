# M02 — referência IBGE e Silver PySpark

Estado: **em desenvolvimento; preparado e testado localmente, ainda sem execução M02 no Fabric**. A Bronze e a repetição M01 permanecem concluídas. Não foi alterada a lógica dos notebooks 01/02.

## Decisões e motivo

Para medir equivalência, usar os mesmos snapshots já perfilados: ANP com hash `a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c` e resposta HTTP IBGE/RJ com hash `2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0`. A data de recebimento original é conservada. A resposta IBGE foi recebida com gzip; a extensão `.http.gz` descreve seus bytes preservados.

Nesta fatia, levaremos o snapshot oficial preservado do IBGE ao Fabric por upload, para não substituir a referência por uma nova resposta da API durante a comparação. Isso não é uma nova ingestão REST executada no Fabric. Uma ingestão periódica do IBGE poderá ser introduzida depois com a mesma disciplina de versões, sem duas fontes canônicas concorrentes.

A validação Python de `fuelwatch/contract.py` é reaproveitada em uma UDF PySpark, com retorno explícito de date, decimal(10,3), strings e motivos. A UDF é executada após filtrar gasolina/RJ na Bronze, não nas 422.418 linhas nacionais. Usa serialização padrão (`useArrow=False`) para não depender da configuração de UDF Arrow da sessão. O código usa a API de Spark 3.5+; o notebook 03 informa a versão efetivamente disponível antes de iniciarmos a Silver.

O contrato compartilhado evita copiar regras de CNPJ/data/preço/município em dois motores. Os testes locais verificam essas regras e o pacote; não demonstram execução distribuída da UDF. Essa parte será exercitada primeiro no fixture do notebook 04. O custo da UDF poderá ser medido no marco de desempenho.

IQR usa Decimal e quartis inclusivos exatos, como no ensaio local. Apenas os preços da fatia aprovada de 8.052 observações são coletados no driver para essa estatística. Antes de expandir o volume ou produtos, rever esse mecanismo; não há aproximação silenciosa por float.

## Arquivos e responsabilidades

| Arquivo | Responsabilidade |
| --- | --- |
| `fuelwatch/m02_reference.py` | Contrato de intercâmbio, leitura do snapshot, IQR decimal e fixture sintético |
| `fuelwatch/silver_spark.py` | Categorias no Spark, sinal de preço incomum, comparação e fixture distribuído |
| `scripts/build_m02_bundle.py` | Conferir baseline, empacotar módulos e dados, gerar notebooks |
| `notebooks/m02_sources/` | Código-fonte das células; alterar aqui e regenerar os notebooks |
| `notebooks/03_ibge_reference.ipynb` | Snapshot IBGE preservado → `ref_municipio_ibge` |
| `notebooks/04_bronze_to_silver.ipynb` | Fixture, categorias, oracle local, publicação e repetição Silver |
| `tests/test_m02_reference.py` | Integridade, tipos, equivalência do fixture e pacote determinístico |
| `evidence/m02/` | Testes/preparação locais; resultados Fabric serão acrescentados após recebidos |

`data/artifacts/m02/` fica fora do Git porque contém os dados e o pacote gerado. Os manifestos e hashes pequenos em `evidence/m02/` ficam versionados. Nenhuma senha é necessária para este upload ou para os notebooks.

## Reproduzir a preparação local

Na raiz do projeto:

```powershell
python -m scripts.build_m02_bundle
python -m unittest discover -s tests -v
```

O gerador confere o hash de negócio do Parquet local, seus snapshots, cobertura, chaves e IQR antes de empacotar. Cada notebook incorpora o hash do manifesto aprovado. Se alterar o contrato/código, regenerar o pacote e os dois notebooks juntos; fazer upload da nova versão e parar as sessões antigas antes de executá-la. Não misturar notebook de uma versão com bundle de outra.

## Bloco 1 — upload e referência IBGE

1. Confirmar que as sessões 01/02 já concluídas estão paradas.
2. No `lh_fuelwatch`, criar `Files/m02_input`.
3. Fazer upload **dos quatro arquivos** de `data/artifacts/m02/` para essa pasta, sem descompactar: `manifest.json`, `fuelwatch_rules.zip`, `municipios-rj.http.gz` e `reference.parquet`.
4. No workspace, importar `notebooks/03_ibge_reference.ipynb`. Anexar `lh_fuelwatch` como padrão e manter os parâmetros gerados se o caminho de upload for o indicado.
5. Executar tudo. O bootstrap confere todos os hashes antes de adicionar o código à sessão Spark. O notebook preserva os bytes IBGE em `Files/raw/ibge_municipios_rj/<hash>/`, publica a referência Delta e compara seus quatro campos com o snapshot.
6. Guardar o JSON final de `Files/audit/ibge/<run_id>.json`. Esperado: `ibge_reference_validated`, 92 municípios, zero ambiguidade e versão Spark/Python registradas. Conferir esse resultado antes de seguir.
7. **Parar a sessão 03**.

## Bloco 2 — fixture e primeira Silver

1. Importar `notebooks/04_bronze_to_silver.ipynb` e anexar o mesmo Lakehouse como padrão.
2. Executar tudo. Primeiro ele reconcilia a referência IBGE já publicada com o snapshot, depois executa o fixture.
3. O fixture contém 14 entregas sintéticas: 9 aceitas (incluindo um preço 99,90), 2 inválidas, 1 duplicata exata excedente e 2 linhas conflitantes após deduplicação. O preço extremo permanece aceito e sinalizado. As duas inválidas são gravadas em `lab_m02_quarantine`, com original, motivos, hash e `is_synthetic=true`.
4. Só depois de aprovar o fixture, a Bronze oficial é filtrada pelo hash e por GASOLINA/RJ. A validação separa inválidos, depois duplicatas exatas, depois conflitos de chave, sem escolher arbitrariamente uma linha conflitante.
5. Diagnósticos oficiais vão para tabelas de histórico por tentativa: `quarantine_preco_anp`, `audit_duplicatas_exatas_anp`, `audit_conflitos_anp`. Essas tabelas podem ganhar auditorias em novas tentativas; não representam observações de negócio duplicadas.
6. A candidata é comparada integralmente ao Parquet local em 13 campos: os 12 campos tipados de observação, incluindo CNPJ/município originais, mais `preco_incomum_iqr`. Metadados de execução, número do registro e texto de serialização do JSON não entram na igualdade de negócio. Os 16 valores originais continuam em `raw_json` e a linha é rastreável por `raw_row_sha256` e hash do ZIP.
7. Um conflito, divergência de categorias, cobertura, tipos ou valores bloqueia a escrita da Silver. Após os checks, a escrita Delta substitui somente o scope_id aprovado. A tabela é relida e comparada com a candidata.

O ordinal lógico do CSV do ensaio local não é fabricado na transformação Spark: a Bronze existente não o contém. A quarentena usa hash da linha + payload original + versão da origem + run_id. Isso localiza o conteúdo; ocorrências idênticas compartilham o hash e sua multiplicidade é contabilizada separadamente.

### Resultado esperado da primeira execução

| Medida | Esperado para os snapshots aprovados |
| --- | ---: |
| Fonte completa | 422.418 |
| Fora do recorte | 414.366 |
| Selecionadas/aceitas | 8.052 / 8.052 |
| Inválidas / duplicatas excedentes / conflitos na fatia | 0 / 0 / 0 |
| Postos / municípios | 502 / 27 |
| Sinais IQR mantidos | 26 |
| IQR inferior / superior | 5.4050 / 7.7650 |
| Diferenças com a referência local | 0 nas duas direções |

Esperado: `status=silver_validated`, `fixture.status=fixture_validated`, `silver_rows=8052`. Na primeira carga, `same_business_as_previous=null` é normal: ainda não havia Silver anterior para comparar. Não significa que a repetição já passou.

## Bloco 3 — repetição Silver

1. Com o mesmo bundle e parâmetros, reexecutar o notebook 04 após a primeira carga verde. Se ainda estiver na mesma sessão, pode usá-la; não iniciar outra sessão em paralelo.
2. Ele fixa a versão Delta anterior, exige os mesmos hashes ANP/IBGE e compara seus 13 campos de negócio com a candidata antes de publicar. Outra origem é bloqueada neste M02; promoção de novas versões pertence ao M03.
3. Após a escrita, compara também a versão anterior com o resultado persistido.
4. Guardar o segundo JSON de `Files/audit/silver/<run_id>.json`. Aceite: `same_business_as_previous=true`, 8.052 linhas, mesmas contagens/cobertura e zero diferenças de negócio. Metadados de run/horário podem mudar.
5. Parar a sessão ao concluir e enviar os JSONs para registrar as evidências e atualizar o roadmap.

## Limites e recuperação

As tabelas de diagnóstico e a Silver não constituem uma transação distribuída: cada escrita Delta é atômica em sua própria tabela. Uma tentativa rejeitada pode deixar diagnóstico novo, mas não deve promover a candidata Silver. Falha depois do commit da Silver requer inspecionar seu histórico e a auditoria antes de decidir a recuperação; não afirmar rollback entre tabelas. O controle de publicação entre camadas será ampliado no M03/M05.

Nenhum Golden/Warehouse é escrito pelo M02. O fixture nunca é anexado à Bronze/Silver oficiais. O upload do snapshot IBGE é um bootstrap reproduzível; o M02 não reivindica uma nova captura REST no Fabric.

Se ocorrer HTTP 430, conferir as sessões concluídas e parar as que ainda retêm recursos antes de tentar novamente. Não ampliar SKU nem criar recurso pago para contornar esse erro sem analisar a condição e obter a autorização exigida.

## Estado dos blocos nesta preparação

| Bloco | Estado | Evidência |
| --- | --- | --- |
| Reconhecimento do contrato e snapshots | COMPLETO | Hashes e baseline local conferidos |
| Código, pacote e checks locais | COMPLETO | 14 testes aprovados, schema dos notebooks e sintaxe conferidos |
| Execução da referência IBGE no Fabric | NAO_FEITO | Depende do upload/execução pelo usuário |
| Fixture, Silver e repetição no Fabric | NAO_FEITO | Depende da referência IBGE validada e dos retornos Spark |
| Marco M02 completo | PARCIAL | Código preparado; aceite de execução ainda aberto |

## Referências

- [API de localidades IBGE](https://servicodados.ibge.gov.br/api/docs/localidades): fonte do snapshot de municípios.
- [Adicionar código Python/ZIP à sessão Spark](https://spark.apache.org/docs/3.5.6/api/python/reference/api/pyspark.SparkContext.addPyFile.html): mecanismo usado para distribuir o contrato aos workers.
- [UDF PySpark](https://spark.apache.org/docs/3.5.6/api/python/reference/pyspark.sql/api/pyspark.sql.functions.udf.html): retorno estruturado com tipos explícitos.
- [Notebooks Fabric e Lakehouse padrão](https://learn.microsoft.com/en-us/fabric/data-engineering/how-to-use-notebook): importação e associação do notebook ao armazenamento.
