# Contrato histórico — primeira ampliação nacional

Escopo: os dois semestres de 2024 e os dois de 2025, preservando a publicação
de 2026H1. A descoberta usa os links da página oficial da série histórica da
ANP; o snapshot do catálogo e cada arquivo são preservados por SHA-256.
`scripts/profile_history.py --refresh` consulta novamente inclusive os arquivos
antigos. Data do nome, Last-Modified e ETag não substituem o hash de conteúdo.

## Layout e unidades observadas

Os quatro arquivos contêm um CSV UTF-8 com as mesmas 16 colunas do contrato
nacional. A chave candidata continua CNPJ/produto/data da coleta/unidade.
O preço é decimal com até três casas; CNPJ é texto, preservando zeros.
O registro bruto guarda a unidade original. Em 2025H2, o GNV usa `R$ / m3`;
essa versão admite sua equivalência explícita a `R$ / m³`, com saída `m3`.
Os demais combustíveis usam litro. Nenhuma conversão entre litro e m³ ocorre.

## Reconciliação local verificada

| Arquivo | Recebidos | Inválidos | Excesso de duplicatas exatas | Registros em conflito | Aceitos |
|---|---:|---:|---:|---:|---:|
| 2024H1 | 477.154 | 0 | 10 | 8 | 477.136 |
| 2024H2 | 421.382 | 0 | 0 | 0 | 421.382 |
| 2025H1 | 429.523 | 9.114 | 0 | 0 | 420.409 |
| 2025H2 | 384.208 | 0 | 0 | 0 | 384.208 |
| Total | 1.712.267 | 9.114 | 10 | 8 | 1.703.135 |

Os 9.114 registros inválidos são totalmente vazios, mas existem fisicamente no
CSV e entram na reconciliação e na quarentena. Nenhum dos oito registros com
chave conflitante é escolhido arbitrariamente. Duplicatas são avaliadas após a
validação: um registro inválido repetido continua contabilizado como inválido.
Preços positivos incomuns permanecem aceitos; o sinal estatístico será calculado
separadamente sobre a versão publicada do conjunto histórico.

Fontes de prova local: `evidence/phase2/history/profile-summary.json` e
`reference-summary.json`. Esses resultados não equivalem a execução PySpark.

## Preparação e execução

1. Descobrir e preservar: `python scripts/profile_history.py`.
2. Referência independente: `python scripts/prepare_history_reference.py`.
3. Bundle verificável: `python scripts/build_history_bundle.py`.
4. Pipeline Copy: `tools/fabric/phase2_history_landing.py` prepara, inicia uma
   tentativa identificada, acompanha seu RunId e verifica os bytes no OneLake.
5. Notebook 11: `tools/fabric/phase2_history_spark.py` prepara e executa o
   processamento de versões. Compara integralmente os campos tipados com a
   referência; guarda Bronze, inválidos, duplicatas e conflitos por arquivo/hash.

O Copy preserva cada tentativa em `landing/anp-history/<source>/<RunId>`.
O notebook preserva o ZIP por hash e escreve tabelas `hist_*`, sem substituir
as tabelas nacionais publicadas. A existência de uma Silver de versão ainda
não constitui promoção da Gold nem fechamento do marco F2-02.
