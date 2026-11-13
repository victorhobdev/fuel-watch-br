# M04 — Gold validada no Warehouse

**Concluído: cinco critérios de aceite, 5/12 marcos do projeto.** Execução realizada pelo agente na guia Fabric autorizada pelo usuário, em 12/11/2026 (America/Sao_Paulo). Timestamps UTC dos resultados atravessam 13/11 e foram preservados nos arquivos.

Em `2026-11-12/` estão os resultados observados. `validation.json` confere 30 condições; `32-validation-first.json` e `32-validation-replay.json` preservam os retornos completos das duas validações. `gold-runtime-result.jpg` mostra as métricas consultadas no Warehouse após a repetição. Os registros de texto contêm somente resultados, sem URLs ou identificadores de ambiente.

## Provas executadas

- Warehouse criado na capacidade trial existente; collation binária UTF-8 confirmada pelo preflight. Nenhuma capacidade paga foi criada ou ampliada.
- Setup, calendário de 181 dias e referência de 92 municípios executados.
- Sete cenários sintéticos aprovados, experimento `C1DC436D-CFB1-461F-924A-3A249E73E41C`: base, repetição, atributo atrasado, correção de atributo, correção apenas de preço, rejeição de conflito e rollback após escritas. Cada cenário compara coletas e intervalos completos; o histórico esperado foi 2/2/4/1/2/2/2 versões, respectivamente.
- Reconciliação do laboratório: zero registros ausentes/adicionais, chaves duplicadas, referências inválidas, sobreposições, associações temporais inválidas ou erros de calendário ISO. Fato e semanal: quatro coletas e soma 26,200.
- Transferência oficial aprovada, lote `4ef52958-b66b-40de-92df-68da53783740`, consumindo `silver_preco_publicado` Delta 0 e snapshot `3da66482-2dad-489f-8450-b7ded2005f3d` do M03. Foram reconciliadas 8.052 coletas, 92 municípios de referência, 181 datas, 518 versões esperadas e 656 grupos semanais esperados. A Silver permaneceu inalterada; a sessão Spark foi encerrada.
- Importação do lote para o stage, publicação oficial e validação completa executadas. Publicação e validação repetidas com o mesmo lote; somente timestamps de publicação/checagem podem mudar.

## Resultado oficial

| Medida consultada/validada | Resultado |
| --- | ---: |
| Fatos de coleta | 8.052 |
| Postos / municípios observados | 502 / 27 |
| Preços incomuns válidos mantidos | 26 |
| Versões observadas de posto | 518 |
| Grupos semanais | 656 |
| Campos de negócio comparados integralmente | 13 |
| Soma de preços na fato | 52.777,200 |
| Soma de preços no semanal | 52.777,200 |
| Coletas somadas no semanal | 8.052 |

As duas execuções retornaram `m04_gold_snapshot_validated`, com o mesmo negócio e linhagem. O contrato inclui fonte, hashes, versão Delta e snapshot. O SCD2 representa mudança **observada**, sem atribuir data jurídica de mudança ao posto.

## Transporte pela interface

O seletor de arquivos da guia não estava disponível para automação. Foi criado o notebook 07 com as mesmas células de código do pacote revisado, acrescidas de um transporte dos seis arquivos por base64. O código colado foi copiado de volta e comparado integralmente, normalizando apenas CRLF/LF. Os bytes dos insumos foram mantidos; o bootstrap conferiu o manifesto aprovado antes do uso. A preparação desse transporte está em `evidence/m04/ui-transport-preparation.json`. Após a execução, o transporte foi removido e o código canônico foi restaurado e comparado integralmente por cópia de volta do editor; a prova está em 2026-11-12/notebook07-source-cleanup.json. O notebook não foi executado novamente nessa limpeza.

Os testes locais do pacote não foram confundidos com execução Fabric: este aceite depende dos resultados reais de SQL/Spark registrados aqui. Segurança com leitor, integração Git, implantação, orquestração e desempenho medido pertencem aos marcos seguintes.
