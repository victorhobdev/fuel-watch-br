# Dados nacionais — ANP, primeiro semestre de 2026

Ampliação solicitada em 13/11/2026. Estado: **Silver e Gold nacionais executadas e validadas no Fabric, publicação repetida e exportação real conferida**. Nenhum recurso pago foi criado.

## Escopo e contagens de referência

O arquivo oficial preservado é o semestre nacional de combustíveis automotivos já ingerido, SHA-256 `a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c`. Não são todos os anos da ANP nem uma nova ingestão GLP.

| Medida | Resultado |
|---|---:|
| Linhas recebidas | 422.418 |
| Duplicatas exatas excedentes | 6 |
| Inválidas / conflitantes no arquivo aprovado | 0 / 0 |
| Coletas aceitas | 422.412 |
| Postos (CNPJ distintos) | 7.963 |
| Municípios com coletas | 417 |
| UFs | 27 |
| Produtos | 6 |
| Versões observadas de posto | 8.159 |
| Grupos semanais municipais/produto/unidade | 50.965 |
| Municípios do snapshot IBGE nacional | 5.571 |

Produtos/unidades: DIESEL, DIESEL S10, ETANOL, GASOLINA e GASOLINA ADITIVADA em BRL/litro; GNV em BRL/m3. Não calcular um preço médio combinando produtos ou unidades diferentes. O levantamento é amostral: 417 municípios com coletas não significa cobertura de todos os municípios ou postos do Brasil.

## Onde trabalhar

No workspace `fuelwatch-dev`, Lakehouse `lh_fuelwatch`:

- `silver_preco_brasil`: coletas nacionais tipadas, campos originais em raw_json, hash, origem, contrato e run_id. Inclui endereço de origem, CEP normalizado e valor de compra tipado quando informado. CNPJ/CEP permanecem texto.
- `ref_municipio_ibge_brasil`: códigos, nomes oficiais, UF e snapshot da referência.
- `ref_limites_iqr_brasil`: quartis e limites por UF/produto/moeda/unidade/semana ISO.
- `quarantine_preco_brasil`, `audit_duplicatas_brasil`, `audit_conflitos_brasil`: categorias de qualidade por tentativa, com dados originais e proveniência. Essas tabelas são auditoria; reexecução pode acrescentar outra tentativa sem criar novas coletas de negócio.

No Warehouse `wh_fuelwatch`, schema `gold_br`:

- `coletas`: consulta plana com município oficial, semana e classificação do preço.
- `business_published`: treze campos de negócio reconciliados integralmente com Silver.
- `fato_preco_coletado`: fato dimensional individual.
- `dim_posto`, `dim_municipio`, `dim_produto`, `dim_data`: dimensões; bandeira é atributo observado do posto.
- `preco_semanal`: agregação por semana ISO/município/produto/moeda/unidade.
- `publication`: versão e origem da publicação atual.

Exemplo: `SELECT TOP (100) * FROM gold_br.coletas ORDER BY data_coleta DESC,uf,produto,cnpj;`

Consultas prontas: `sql/national/04_analysis_queries.sql`. No Spark: `spark.table("silver_preco_brasil")`.

O schema `gold` e a Silver RJ anteriores permanecem como baseline da fase 1; não representam o novo conjunto nacional. O relatório Power BI da fase 1 continua restrito ao RJ/GASOLINA até sua ampliação explícita. Isso não limita as novas tabelas para SQL/Spark.

## Qualidade e município

A chave de coleta foi verificada no arquivo completo: CNPJ + produto + data + unidade. Seis duplicatas exatas foram separadas; nenhum conflito permaneceu. Também foi verificada a ausência de atributos conflitantes do mesmo posto no mesmo dia entre produtos.

Há 830 registros ANP com município RS/SANTANA DO LIVRAMENTO. A referência IBGE registra a grafia com apóstrofo. O alias é explícito para o código 4317103 e só é aceito após conferir nome/UF no snapshot oficial. Não foi feito fuzzy matching nem escolha arbitrária de município.

A quarentena recebe inválidos; preços incomuns continuam válidos. O IQR nacional é calculado independentemente em Pandas e Spark com quartis lineares exatos em milésimos inteiros, agrupando UF/produto/moeda/unidade/semana ISO. Exige pelo menos vinte coletas e cinco postos por grupo. Os 11.366 sinais incomuns são preservados; 8.657 linhas pertencem a grupos sem cobertura suficiente para avaliação. `iqr_avaliado=false` não significa preço normal. No Warehouse, `classificacao_preco` distingue `nao_avaliado`, `incomum_valido` e `valido_sem_sinal`.

O método de IQR mudou em relação à fatia RJ, que calculava um limite do semestre. Portanto, o número de flags não é comparável diretamente com os 26 antigos; os preços e suas chaves continuam preservados.

## Reprodução e verificação

1. `python -m scripts.download_national_reference`: obter snapshots oficiais municipais/UFs, preservando resposta HTTP comprimida e JSON decodificado com hashes próprios.
2. `python -m scripts.prepare_national`: perfilar/validar toda a entrada e construir referência local independente, histórico observado, calendário e semanal. O script requer o ZIP previamente preservado no ledger do projeto; não baixa outra versão silenciosamente.
3. `python -m scripts.build_national_bundle` e `python -m scripts.build_national_sql`: gerar bundle imutável e notebook/T-SQL revisáveis.
4. `python -m scripts.check_national_relational`: comparar histórico e semanal completos em DuckDB; isso não equivale a execução Fabric.
5. Com o Python operacional, `tools/fabric/national_job.py --prepare`, depois `--start`; guardar o ID aceito. Se o monitoramento cair, usar `--watch <job_id>`, sem repetir POST.
6. `tools/fabric/national_warehouse.py <job_id>`: exigir job Spark concluído, identificar um único recibo na janela de execução, aguardar visibilidade SQL do mesmo run e publicar transacionalmente após validar todas as entradas. `--replay` é uma repetição explícita da publicação do mesmo run.

Uma operação HTTP aceita não prova dados publicados. A publicação nacional foi aceita após a comparação integral dos treze campos, das 8.159 versões e dos 50.965 grupos com a referência independente, além de contagens/somas por UF/produto/unidade. As tabelas nacionais têm nomes próprios para não invalidar os checks históricos fixos de 8.052 coletas; o baseline RJ é conferido antes/depois.


## Resultados e arquivos prontos

Run Spark `e0777690-df6b-4317-ab22-b11e76be43ed`; publicação `7e2b22fc-6fb4-4237-8481-bbc79c753103`. Repetição explícita da mesma publicação validada sem mudança de negócio. [Evidências](../evidence/fabric/national/7e2b22fc-6fb4-4237-8481-bbc79c753103/warehouse-verification.json).

| Produto | Coletas válidas | Unidade |
|---|---:|---|
| GASOLINA | 110.923 | BRL/litro |
| GASOLINA ADITIVADA | 86.231 | BRL/litro |
| ETANOL | 93.891 | BRL/litro |
| DIESEL | 45.814 | BRL/litro |
| DIESEL S10 | 77.116 | BRL/litro |
| GNV | 8.437 | BRL/m3 |

Arquivos locais extraídos da view real `gold_br.coletas`, com 422.412 linhas e dezessete colunas:

- `data/processed/anp_brasil_2026_1.parquet`: aproximadamente 6 MB, CNPJ textual, preço decimal(10,3), datas e booleanos tipados.
- `data/processed/anp_brasil_2026_1.csv.gz`: aproximadamente 10 MB, UTF-8 BOM, separador ponto e vírgula e vírgula decimal. Ao importar, declarar CNPJ/código IBGE como texto para preservar zeros.

Exemplo Python: `pd.read_parquet("data/processed/anp_brasil_2026_1.parquet")`. Para CSV: `pd.read_csv("data/processed/anp_brasil_2026_1.csv.gz", sep=";", decimal=",", dtype={"cnpj":"string","cnpj_origem":"string","municipio_ibge":"string"})`.

A Silver no Lakehouse tem também raw_json e os campos de endereço/CEP de origem; o arquivo plano acima corresponde aos campos de consumo Gold. Os dados ficam fora do Git, mas os hashes, schema e checagens de exportação são [versionáveis](../evidence/fabric/national/export-verification.json).

O pipeline mestre da fase 1 e o relatório anterior continuam apontando para o baseline RJ. O fluxo nacional foi executado pela CLI (`national_job.py` → `national_warehouse.py`), com recibos próprios; não foi alegado agendamento automático nacional nem expansão do relatório. Essa separação preserva as evidências antigas e deixa os dados nacionais disponíveis imediatamente para consultas.

O refresh seletivo do SQL endpoint respondeu `NotRun` com timestamps de sincronização anteriores: a sincronização já havia ocorrido. Não se atribui a essa chamada uma correção que ela não executou. A publicação exigiu os dados do run exato visíveis antes de iniciar.
