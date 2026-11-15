# Fuel Watch BR

Projeto pessoal para aprender Microsoft Fabric e praticar competências da DP-700 com dados públicos de preços de combustíveis. Explicações e registros em português; nomes de ferramentas preservados como aparecem na interface.

## Ampliação nacional — dados disponíveis

O mesmo arquivo ANP de jan–jun/2026 já está tratado para **todas as 27 UFs e os seis produtos presentes**: **422.412 coletas válidas, 7.963 postos e 417 municípios observados**. Seis duplicatas exatas separadas; GNV em BRL/m3, demais produtos em BRL/litro.

No Fabric: Lakehouse `lh_fuelwatch`, tabela `silver_preco_brasil`; Warehouse `wh_fuelwatch`, view **`gold_br.coletas`**, dimensões e agregado `gold_br.preco_semanal`. Silver/Gold, referência independente completa, repetição da publicação e exportação real foram validadas. [Guia dos dados, consultas e arquivos Parquet/CSV](docs/dados-nacionais.md), [evidências](evidence/fabric/national/).

[Roadmap vigente da fase 2 em cinco marcos](docs/roadmap-fase2-cinco-marcos.md): **F2-01 a F2-04 concluídos; F2-05 em fechamento**. O plano anterior de dez itens permanece como detalhamento histórico.

O observatório nacional agora tem sete visões `analise_br`, modelo DirectQuery e relatório **Fuel Watch BR Nacional**, com páginas de panorama e postos/bandeiras. As visões foram comparadas integralmente com referência independente; filtros e medidas foram reconciliados em SQL/DAX e quatro recortes foram renderizados e inspecionados. [Seis respostas interpretadas](docs/phase2-respostas-analiticas.md), [contrato analítico](docs/analytics-contract.md) e [aceite F2-01](evidence/phase2/analytics/acceptance.json).

O histórico de 2024–2025 foi processado no Spark e publicado junto de 2026H1 no Warehouse: **2.125.547 coletas, 13.030 postos, 462 municípios, 27 UFs e seis produtos**, em `gold_hist`. Referência/Silver/Gold, operação integrada, repetição, correção antiga isolada, falha e recuperação foram reconciliadas; a agenda finita foi executada e desabilitada. As sete visões `analise_hist`, contexto populacional/climático, modelo DirectQuery e quatro páginas do relatório histórico também foram reconciliados e renderizados. O rebuild em workspace vazio da mesma trial reproduziu a publicação. [Guia dos dados históricos](docs/dados-historicos.md), [análises e limites](docs/analytics-contract.md), [PDF conferido](evidence/phase2/deployment/rebuild-history-report-qa4.pdf), [andamento por marco](evidence/phase2/progress.json). O último marco fecha CI, inventário de dependências e auditoria final de recursos.

O registro M00–M11 abaixo documenta o aceite anterior; a fase 2 amplia o histórico e o consumo com os artefatos acima.

## Estado da etapa M00–M11 verificado em 13/11/2026

O processamento oficial está validado no Fabric: ANP preservada por SHA-256, Bronze com 422.418 registros, Silver com **8.052 coletas, 502 postos e 27 municípios**, Gold com 518 versões observadas de posto e 656 grupos semanais. A coleta individual permanece disponível antes da agregação semanal. A primeira fatia é GASOLINA, RJ, janeiro a junho de 2026.

| Marco | Evidência atual |
| --- | --- |
| M00–M04: fontes, camadas, correções e SCD2 | Aceitos; cenários reais e sintéticos identificados nas evidências |
| M05: orquestração | Sete tentativas reconciliadas, incluindo falhas, recuperação, repetição e agenda |
| M06: Dataflow Gen2 | Baseline, repetição, falha de contrato e recuperação reais; 92 municípios IBGE |
| M07: segurança | Aceito por revisão de fonte/configuração real; testes com segunda conta dispensados pelo usuário e não executados |
| M08: Git e implantação | Aceito: CI, Git nativo seletivo do notebook 08, promoção dev → test, recuperação e restauração reconciliadas |
| M09: desempenho | Seis medições em dev e seis em test após restauração, com igualdade integral |
| M10: streaming | 1.000 IDs reconciliados, 20 duplicatas, 10 atrasados, quatro consultas KQL e disparo real do Activator |
| M11: consumo | Aceito: DirectQuery, cinco medidas SQL, PDF conferido, documentação e inventário final |

O laboratório sintético é separado dos dados oficiais. A regra Activator foi desligada e os destinos Eventstream pausados após a verificação. Usa-se a capacidade trial existente; não foi contratada capacidade paga. A data de expiração da trial e o consumo em CU não foram verificados.

A execução usa CLI/API, OneLake e ODBC, com bindings e tokens fora do Git. Consulte [roadmap](docs/superpowers/plans/2026-11-12-fuel-watch-br-roadmap.md), [índice de evidências](evidence/README.md), [implantação](docs/deployment.md), [segurança](docs/security-matrix.md), [consumo](docs/consumption.md), [dicionário](docs/data-dictionary.md) e [demonstração](docs/demo.md). **12/12 marcos aceitos no escopo vigente.** O usuário substituiu os testes com leitor pela revisão de implementação M07; comportamento restrito não foi testado. O M08 sincronizou pelo Fabric o notebook 08 no commit `6a30720`, conferido por comparação da árvore sintática do código; os outros 23 itens não foram incluídos nesse envio seletivo. [Status consolidado](evidence/project-status-2026-11-13.json).

Verificação do workflow atualizado: recibo CI em `evidence/phase2/deployment/`. O runner é self-hosted efêmero; a auditoria final cobre jobs, sessões Spark, agendas e destinos dos workspaces do projeto.

Os dados são amostrais. Ausência de observação não representa preço zero nem cobertura de todos os postos. SCD2 registra mudança observada na referência, sem inferir a data histórica real de mudança do estabelecimento.

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

Fonte dos preços: ANP, Levantamento de Preços de Combustíveis. Fonte dos códigos municipais: IBGE. Processamento: Fuel Watch BR. A página da ANP apresenta aviso geral CC BY-ND 3.0; não identificamos uma licença específica adicional no arquivo de metadados. O repositório privado contém código e evidências selecionadas, não os arquivos-fonte, e não atribui licença própria a eles. Condições de qualquer redistribuição pública dos dados devem ser revistas antes de publicar material fora do repositório privado.
