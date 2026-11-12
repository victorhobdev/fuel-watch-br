# Fuel Watch BR

Projeto pessoal para aprender Microsoft Fabric e praticar competências da DP-700 com dados públicos de preços de combustíveis. Explicações e registros em português; nomes de ferramentas preservados como aparecem na interface.

## Estado em 12/11/2026

O projeto começou nesta pasta, que continha somente um Git vazio, sem commits e sem remoto. Nenhum outro projeto foi alterado. Nenhum recurso pago foi criado.

| Entrega | Estado comprovado |
| --- | --- |
| ANP, IBGE e metadados oficiais | Baixados localmente; bytes preservados por SHA-256 e manifesto |
| Perfil do CSV completo | Executado: 422.418 linhas e 16 colunas |
| Primeira fatia | Gasolina comum, RJ, janeiro a junho de 2026 |
| Saída local tipada | Parquet: 8.052 coletas, 502 postos, 27 municípios |
| Idempotência local | Duas execuções reais com o mesmo hash de estado de negócio |
| Correção antiga e recuperação | Testadas com fixtures sintéticos identificados |
| Bronze Delta no Fabric | Saída de execução fornecida pelo usuário: bronze_validated; 422.418 registros, hash e tamanho reconciliados com o perfil local |
| Repetição da Bronze no Fabric | Validada pelo JSON recebido: versões Delta 0 e 1, 422.418 linhas, mesmo esquema e nenhum registro ausente/adicional nas 16 colunas de origem |
| Acesso Azure | Portal confirmado; assinatura exibida como Azure for Students e papel Owner; saldo não verificado; CLI com token expirado na última consulta |
| Acesso ao Fabric | Login mostrado em captura do portal; avaliação de 60 dias informada pelo usuário |
| Lakehouse | Criação informada pelo usuário; detalhes da capacidade e do workspace ainda não registrados |
| Pipeline / Copy | Status Bem-sucedido informado pelo usuário; ZIP de landing identificado na auditoria Bronze recebida |
| Silver Delta | Duas execuções validadas pelos JSONs recebidos: Delta 0 → 1, 8.052 coletas, 502 postos, 27 municípios e mesmo negócio; comparação integral local sem diferenças |
| Warehouse Gold | Ainda não implementado/validado no Fabric |
| M04 — Gold e SCD2 | [T-SQL e modelo preparados](docs/data-model.md); ensaio local real com 8.052 coletas, 518 versões observadas e reconciliação sem diferenças; execução Fabric pendente |
| M02 — IBGE e Silver | CONCLUÍDO: IBGE, fixture distribuído, primeira Silver e repetição validados; cinco de cinco critérios aceitos |
| M03 — Versões e backfill | [Laboratório Fabric validado](evidence/fabric/versioning/README.md): 17 cenários; [notebook 06 entregue](docs/m03-official.md) para seleção oficial/repetição, execução pendente |
| SCD2, segurança, implantação e streaming | Etapas posteriores; sem resultado reivindicado |

Os dados são amostrais. Ausência de observação não representa preço zero nem cobertura de todos os postos. A saída inicial preserva a coleta individual; não é uma fato semanal.

M02 concluído pelos retornos recebidos do Fabric: referência IBGE, fixture, Silver e repetição aceitos. M03 em andamento: laboratório sintético validado no Fabric; integração da seleção de versões ao fluxo oficial pendente. [Guia do M02](docs/m02-silver-ibge.md). O [resumo de 11/11](docs/retomada-2026-11-11.md) conserva o checkpoint anterior.

[Roadmap completo e acompanhamento por marcos](docs/superpowers/plans/2026-11-12-fuel-watch-br-roadmap.md): 3 de 12 marcos concluídos; M03 com laboratório Fabric aceito e integração oficial aberta.

## Reproduzir o bloco local

Python 3.13.5 foi o ambiente observado. pandas e PyArrow já estavam disponíveis; não instalamos Spark nem modificamos a instalação global. Para outro ambiente, crie uma `.venv` e instale `requirements-local.txt` nela.

Execute na raiz do repositório:

```powershell
python -m pip install -r requirements-local.txt
python -m scripts.download_sources
python -m scripts.profile_sources
python -m scripts.prepare_local_slice
python -m scripts.prepare_local_slice
python -m unittest discover -s tests -v
```

O download exige rede, usa apenas URLs de `config/sources.json` e consulta novamente o conteúdo mesmo para semestres antigos. Uma entrega idêntica gera nova auditoria de download, reutilizando os bytes já preservados. Uma entrega diferente fica em outra pasta por hash.

`data/raw/` contém os arquivos originais. `data/manifest/downloads.jsonl` registra os downloads. `data/local/<scope_id>/<run_id>/` contém Parquet, quarentena, duplicatas, conflitos, auditoria e uma consulta agregada por município. `current.json` aponta para a execução local concluída. O formato da consulta é JSON para inspeção; médias são de preços observados, sem ponderação por volume de vendas.

Os arquivos de dados ficam fora do Git. Os relatórios pequenos em `evidence/` são evidências locais reais e podem mudar em uma nova execução. Há regras e tipos explícitos no [contrato mínimo](docs/contrato-minimo.md), resultados no [registro do bloco inicial](docs/bloco-01.md) e instruções para a próxima execução no [roteiro Fabric](docs/fabric-primeira-execucao.md).

## Desenho a validar no Fabric

```text
ANP → Pipeline / Copy (Binary) → Lakehouse Files (ZIP original + manifesto)
    → Notebook → Bronze Delta (strings + metadados)
    → Notebook PySpark → Silver Delta (coletas validadas)
    → Warehouse Gold (T-SQL, dimensões e fato de coleta)
    → consumo semanal derivado / Power BI enxuto

IBGE localidades → referência de municípios identificada por snapshot
```

A Copy activity preservará o arquivo, e o notebook fará a extração e a interpretação. Isso separa transporte de dados e regras de negócio. O ensaio Python local serve para validar a fonte e as regras; ele não substitui a execução dos componentes do Fabric.

Na etapa de confiabilidade, precisamos definir o marcador de versão ativa, promoção controlada de Silver para Gold, reprocessamento por escopo, SCD2 de mudanças observadas e reconciliação entre granularidades. O manifesto de download ainda não é um catálogo transacional de publicação no Fabric.

Git remoto, integração do workspace e implantação entre ambientes permanecem no escopo. Segurança, monitoramento e diagnóstico acompanharão as execuções. Eventstream, Eventhouse, KQL e Activator usarão eventos sintéticos separados, posteriormente. Clima, predição e aplicação web estão fora da primeira fatia.

## Fontes e atribuição

- [ANP — série histórica e downloads](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/serie-historica-de-precos-de-combustiveis).
- [ANP — metadados vigentes consultados](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/metadados-serie-historica-precos-combustiveis-1.pdf).
- [IBGE — API de localidades](https://servicodados.ibge.gov.br/api/docs/localidades).

Fonte dos preços: ANP, Levantamento de Preços de Combustíveis. Fonte dos códigos municipais: IBGE. Processamento: Fuel Watch BR. A página da ANP apresenta aviso geral CC BY-ND 3.0; não identificamos uma licença específica adicional no arquivo de metadados. O repositório não redistribui os arquivos-fonte nem atribui licença própria a eles. O uso neste bloco foi local; condições de uma futura publicação precisam ser revistas antes dela. Nenhum repositório foi publicado.
