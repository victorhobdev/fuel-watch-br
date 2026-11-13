# M04 — Gold dimensional e histórico observado

**Estado em 13/11/2026: M04 executado e aceito no Fabric.** Sete cenários, reconciliação integral e repetição estão em [evidências Gold](../evidence/fabric/gold/README.md). O desenho abaixo registra as decisões do pacote; a Gold oficial tem 8.052 coletas, 518 versões observadas e 656 grupos semanais. O pacote consome o contrato oficial M03 e fixa a Silver por versão Delta/snapshot. Para reproduzir, seguir o [roteiro M04](m04-fabric.md).

## Decisões e verificações

| Decisão | Motivo | Como verificar |
| --- | --- | --- |
| Warehouse independente | As tabelas Gold precisam de DDL/DML T-SQL | Confirmar tipo do item no workspace; não confundir com SQL analytics endpoint |
| Primeiro usar schema `lab_m04` | Executar casos sintéticos sem alterar tabelas oficiais | Conferir schema de todos os scripts; não existe escrita em `gold` ou no Lakehouse |
| Uma coleta por CNPJ/produto/data/unidade | Preservar a granularidade validada na Silver | Zero chaves duplicadas e comparação bidirecional dos 13 campos de negócio |
| Preço `decimal(10,3)` e IQR preservado | Conservar precisão e preços apenas incomuns | 8.052 preços íntegros e 26 sinais no baseline local |
| Histórico por datas de observação | ANP informa atributos vistos na coleta, não a data jurídica da mudança | Fixture com início/fim explícitos e zero associação ambígua |
| Reconstruir o escopo completo inicialmente | Atrasos e correções antigas podem mudar intervalos e fatos já publicados | Fixture altera janeiro mantendo junho; repetição preserva o negócio |
| Transação dentro do Warehouse | Evitar publicar dimensões e fato parcialmente | `TRY/CATCH`, rollback e teste de falha no Fabric; teste local não comprova essa propriedade no Fabric |
| Calendário ISO materializado | Evitar dependência de idioma/`DATEFIRST` e ano civil | Teste 01/01/2021 pertence a 2020-W53; conferir calendário também em T-SQL |

O suporte e as diferenças de DDL/DML foram consultados na [superfície T-SQL](https://learn.microsoft.com/en-us/fabric/data-warehouse/tsql-surface-area). A [documentação de transações](https://learn.microsoft.com/en-us/fabric/data-warehouse/transactions) descreve agrupamento atômico de escritas no Warehouse. Isso não representa uma transação envolvendo commits Spark no Lakehouse.

## Modelo

```mermaid
erDiagram
    dim_data ||--o{ fato_preco_coletado : data_sk
    dim_produto ||--o{ fato_preco_coletado : produto_sk
    dim_municipio ||--o{ fato_preco_coletado : municipio_ibge
    dim_posto ||--o{ fato_preco_coletado : posto_sk
```

| Objeto em `lab_m04` | Chave e significado |
| --- | --- |
| `stage_coleta` | Os 13 campos tipados de negócio da Silver; snapshot completo, congelado durante a carga |
| `stage_manifest` | Uma linha: batch_id, scope_id, tabela de origem, snapshot_id, hashes ANP/IBGE, versão Delta, is_synthetic e contagens esperadas |
| `dim_data` | `data_sk=AAAAMMDD`; dias de 01/01 a 30/06/2026, início de semana, ano/semana ISO |
| `dim_produto` | `produto_sk=1` nesta fatia restrita: GASOLINA/BRL/litro; outros produtos/unidades bloqueados |
| `dim_municipio` | Código IBGE textual de sete posições; nome/UF do snapshot identificado por hash |
| `dim_posto` | `posto_sk=cnpj:AAAA-MM-DD`, com início observado da versão; nome, bandeira, município e UF observados |
| `fato_preco_coletado` | FKs, preço, IQR, textos originais CNPJ/município e batch_id; sem agregação |
| `business_published` | Reconstrói os 13 campos originais por joins dimensionais para reconciliação |
| `stage_business_bytes`, `published_business_bytes` | Representações binárias de textos para comparar também espaços finais |
| `preco_semanal` | Semana ISO/município/produto/moeda/unidade: coletas, postos, soma, média, mínimo, máximo e sinais |
| `publication` | Seleção publicada atual e sua proveniência; não é o histórico completo de tentativas |

A chave de posto é técnica e determinística para o CNPJ/início de intervalo. Uma correção pode apagar um início antigo; seus fatos são reassociados na mesma reconstrução. Não é uma promessa de SK permanente entre todos os snapshots. O identificador 1 de produto é delimitado a esta fatia, não um cadastro genérico já resolvido.

As [constraints no Warehouse](https://learn.microsoft.com/en-us/fabric/data-warehouse/tables) são `NOT ENFORCED`; por isso o código usa checks de unicidade e referências. Os [tipos persistidos suportados](https://learn.microsoft.com/en-us/fabric/data-warehouse/data-types) orientaram `varchar` UTF-8, `date`, `decimal` e `datetime2(6)`. O laboratório exige collation `Latin1_General_100_BIN2_UTF8`; se o item tiver outra, revisar antes de executar. O procedimento bloqueia a carga nesse caso.

## SCD2: o que os intervalos significam

Para cada CNPJ, ordenar os atributos observados por `data_coleta`. Repetições consecutivas do mesmo conjunto não abrem uma versão. Mudança de nome, bandeira, município ou UF inicia uma nova versão naquela data. A anterior termina na mesma data: **[observado_desde, observado_ate)**. `observado_ate=NULL` identifica o último estado observado no snapshot.

Um fato em 19/01 pertence à versão iniciada em 19/01, não à que termina nesse dia. Antes da primeira coleta não há versão inferida. Entre coletas, o uso do último estado observado é uma convenção analítica explícita; não comprova quando ocorreu a alteração real. O último estado observado tampouco comprova a situação atual do posto fora da cobertura temporal.

Exemplo sintético: bandeira A em 05/01 e 12/01; B em 19/01 e junho. Uma observação atrasada C em 08/01 cria a sequência A → C → A → B. Corrigir B para A nas observações de 19/01/junho pode eliminar uma transição. Corrigir somente preço não abre versão de posto. Atributos diferentes no mesmo CNPJ/data bloqueiam a carga: a origem não informa horário para decidir uma ordem.

Esta é a linha do tempo das observações **segundo o snapshot selecionado**. Correções podem reconstruí-la. Não é um modelo bitemporal de “o que sabíamos em cada dia de processamento”. Para reconstruir estados anteriores é necessário manter entradas, manifesto e evidências por execução; `publication` conserva apenas a seleção atual. Não usar o horário de execução como início fictício de mudança do posto.

## Resultado local real

O script `python -m scripts.prepare_m04_gold` verificou o manifesto M02 e os hashes dos arquivos antes de ler o Parquet de referência. Usou os dados reais preservados; não consultou tabelas do Fabric.

- 8.052 coletas, 502 postos, 27 municípios e 26 preços incomuns preservados.
- 518 versões observadas de posto. Os 14 CNPJs com mais de uma bandeira produziram 16 transições; nenhuma mudança de nome ou município nessa referência.
- Zero ambiguidades de atributos por CNPJ/data, sobreposições, chaves duplicadas, referências ausentes ou diferenças dos 13 campos.
- 656 grupos semanais. Soma de preços e quantidade de coletas reconciliadas; repetição local manteve história e fatos.

O detalhamento por versão e os agregados ficam em Parquet em `data/artifacts/m04/<run_id>/`, fora do Git. O resumo rastreável é [local-gold.json](../evidence/m04/local-gold.json). Esses achados descrevem observações no arquivo; não provam alterações cadastrais reais.

## Semana, média e cobertura

A semana começa na segunda-feira; usar também ano ISO e data de início. A primeira semana do recorte pode começar em dezembro de 2025 e a última terminar em julho de 2026. As observações continuam limitadas ao semestre: não completar dias ausentes com zeros. Semanas nas bordas são parciais.

A média é `SUM(preco_venda)/COUNT(coletas)`; não representa volume vendido. Para reunir grupos, somar `soma_precos` e dividir pela soma de `coletas`. Não calcular média simples das médias. `postos_observados` é distinto dentro de cada grupo e não é aditivo entre semanas/municípios. Os 27 municípios observados são cobertura da amostra; o snapshot IBGE tem 92 municípios e não informa quantos postos deveriam ter sido coletados.

## Roteiro operacional

O [roteiro M04](m04-fabric.md) é a sequência única de execução, com arquivos completos, campos para editar, resultados esperados, retomada e evidências. O builder reúne as views em batches dinâmicos; não é necessário recortá-las manualmente. O caminho é seleção oficial M03 no 06 → laboratório `lab_m04` → notebook 07 → importação por batch_id → publicação em `gold` → validação → repetição.

O notebook aceita somente um `consumer_contract` M03 bem-sucedido compatível com a seleção ativa, fixa essa versão Delta, compara os 13 campos com o baseline e exporta tabelas `m04_transfer_*`; o manifesto do lote é escrito por último. O SQL importa somente o lote indicado, com 8.052 coletas, 92 municípios IBGE, 181 datas, 518 intervalos esperados e 656 grupos semanais esperados. Não consome todas as versões nem aceita silenciosamente uma Silver alterada.

`gold.expected_posto` e `gold.expected_weekly` são tabelas auxiliares de validação carregadas do oracle preservado por hash; não são dimensões adicionais nem resultados produzidos pelo próprio procedimento T-SQL. O laboratório tem suas próprias expectativas e registros em `lab_m04.fixture_checks`, por experimento.

Todos os registros oficiais vão para o schema `gold`; fixtures ficam em `lab_m04`. A publicação oficial, seus metadados e a comparação são verificáveis pelos scripts finais. Execução serial; controle concorrente e recuperação geral entre camadas serão aprofundados no M05.

Uma consulta entre Warehouse e SQL analytics endpoint pode usar nomes de três partes no mesmo workspace, conforme [documentação](https://learn.microsoft.com/en-us/fabric/data-warehouse/query-warehouse). Isso não seleciona por si uma versão Delta histórica nem comprova que a sincronização do endpoint já terminou. Por isso o adaptador dependerá de snapshot de transferência verificado, com referência ao M03.

## Verificação local e limites

```powershell
python -m unittest tests.test_gold_local -v
python -m scripts.prepare_m04_gold
```

DuckDB 1.5.2 já estava instalado; foi declarado em `requirements-local.txt`, sem instalação ou alteração global. O harness executa as views do arquivo 02 e a reconciliação relacional do 04. Adapta tipos (`bit`, `datetime2`), `COUNT_BIG`, `DATALENGTH` e conversões binárias explicitamente; não executa o procedimento T-SQL, a gestão transacional do Fabric ou `GO`/DDL condicional. O ensaio preserva valores e multiplicidades com `EXCEPT ALL`. No procedimento preparado, chaves únicas, associação temporal, contagem e comparação binária bidirecional compõem o check.

Os testes locais não fecham critérios do roadmap que exigem Fabric. Compilação T-SQL, semântica de collation, transferência, rollback real e comparação das saídas sintéticas continuam pendentes de execução. O adaptador e a publicação oficial do baseline estão preparados no pacote; não há resultado Gold em nuvem reivindicado.
