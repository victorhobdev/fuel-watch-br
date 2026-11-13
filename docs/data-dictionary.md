# Dicionário mínimo — Fuel Watch BR

## Origem e camadas

| Camada/objeto | Grão e contrato |
|---|---|
| Landing/raw | ZIP oficial nacional completo, preservado por conteúdo; URL, SHA-256, tamanho e execução identificados |
| Bronze | Uma ocorrência do CSV, strings originais e metadados; 422.418 registros para o hash aprovado |
| Referência IBGE | Snapshot de 92 municípios RJ, código textual de sete posições e hash da resposta preservada |
| Silver M02 | Coletas tipadas no recorte GASOLINA/RJ, 01/01–30/06/2026; baseline usado na reconciliação |
| Silver publicada M03 | Versão/snapshot selecionados explicitamente para consumo; correções antigas não dependem de MAX(data) |
| Gold fato | Uma coleta individual com chaves dimensionais e preço; 8.052 fatos no snapshot aceito |
| Gold histórico de posto | Versão de atributos observados por CNPJ e intervalo semiaberto; 518 versões, não 518 postos |
| Gold semanal | Semana ISO + município + produto + moeda + unidade; 656 grupos; derivado da fato individual |
| Power BI | View de consumo das coletas + semana, medidas explícitas e filtro comum; sem nova fonte oficial |

## Campos de negócio

| Campo | Tipo/semântica | Verificação |
|---|---|---|
| `cnpj` | Texto com 14 posições; zeros à esquerda preservados | Não converter para número; 502 distintos no recorte |
| `cnpj_origem` | Representação original ANP | Preservar para rastreabilidade |
| `produto` | GASOLINA nesta fatia | Comparar produto/unidade antes de combinar observações |
| `data_coleta` | `date`, data da observação | Não substituir pela semana ou data de ingestão |
| `preco_venda` | `decimal(10,3)`, BRL por litro | Positivo e parseável; preço incomum não é automaticamente inválido |
| `moeda` / `unidade` | BRL / litro | Unidade ANP normalizada a partir de `R$ / litro` |
| `uf` | RJ | Escopo contratual desta entrega |
| `municipio_ibge` | Código textual de sete posições | Correspondência única no snapshot de referência |
| `municipio_origem` | Nome coletado na ANP | Preservado sem inventar correspondência ambígua |
| `revenda_observada` / `bandeira_observada` | Atributos vistos na coleta | SCD2 representa mudança observada; não data jurídica da alteração |
| `preco_incomum_iqr` | Sinal de preço estatisticamente incomum | 26 sinais no baseline; não é meta universal nem quarentena |

A chave candidata validada na entrega é CNPJ + produto + data de coleta + unidade. Arquivos novos exigem validar novamente duplicatas exatas e conflitos dessa chave. Inválidos retêm original/motivo; conflitos não são resolvidos por escolha arbitrária.

## Linhagem e operação

`source_sha256` identifica conteúdo ANP; `ibge_sha256` identifica referência; `scope_id` delimita o recorte; `snapshot_id` identifica seleção; versão Delta fixa a leitura. `run_id`/`root_run_id` são tentativas, não versões de negócio; `batch_id` relaciona exportação/importação/publicação. Repetir conteúdo pode gerar nova auditoria e novo commit Delta sem alterar o multiconjunto de negócio.

`observado_desde` inclui a data inicial; `observado_ate` exclui a data final e pode ser NULL na última versão. Correção/atraso pode reconstruir intervalos anteriores e reassociar fatos. A SK técnica não é promessa de identidade permanente entre todas as reconstruções.

`is_synthetic=true` identifica laboratórios/fixtures. Eventos M10 têm `event_id`, `lab_run_id`, `posto_id=SYNTHETIC_*`, `event_time` UTC, produto/unidade/moeda e preço fictício. `ingestion_time()` é tempo do serviço, distinto do evento; a deduplicação é por lote/ID. Esses eventos nunca são apresentados como streaming da ANP.
