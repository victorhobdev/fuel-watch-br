# Executar M04 no Fabric — roteiro completo da seleção oficial

**M04 executado e validado no Fabric: cinco critérios aceitos.** [Evidências reais](../evidence/fabric/gold/README.md): sete cenários, transferência oficial, publicação, reconciliação integral e repetição. Este roteiro permite reproduzir a execução. O [modelo e a semântica SCD2](data-model.md) explicam as decisões. Não usar os artefatos antigos de `data/artifacts/m04/<run_id>` como sequência manual: o pacote abaixo já contém instalação, testes e validação agrupados.

O notebook **05** cobre o laboratório M03; o **06_official_source_selection** seleciona a origem oficial e devolve um `consumer_contract`. O M04 consome esse contrato na tabela **silver_preco_publicado**, fixando a versão Delta e o `snapshot_id` aprovados. Ele também reconcilia os 13 campos com o baseline revisado no M02. Não confundir a versão Delta dessa nova tabela com a versão 1 de `silver_preco_coletado`: tabelas diferentes têm históricos distintos. Uma mudança de conteúdo requer revisão do pacote; não alterar hashes/versão para forçar execução.

## O que está pronto

- Notebook `notebooks/07_export_gold_input.ipynb`, importável; não instalar bibliotecas na sessão.
- Seis arquivos de upload em `data/artifacts/m04_fabric/upload/`.
- Nove scripts numerados em `data/artifacts/m04_fabric/warehouse/`.
- Comparação automática de todos os fatos, de todas as 518 versões esperadas e dos 656 grupos semanais, além dos testes sintéticos. As expectativas vêm do ensaio local com o snapshot real identificado por hash.

Não criar capacidade paga. Reusar o trial e o workspace do projeto. O roteiro não cria recursos Azure nem autoriza uso de crédito. Um Warehouse novo só deve usar a capacidade trial já confirmada; se houver indicação de cobrança/upgrade, parar e avaliar custo antes de criar.

## A — Confirmar e preparar o Warehouse

1. Concluir o notebook **06_official_source_selection** do M03 e guardar seu JSON **m03_official_selection_validated**, com `consumer_contract`. Usar **Stop session**. O laboratório 05 sozinho não produz a seleção oficial necessária para este M04.
2. Identificar o item **Warehouse** exclusivo deste projeto. O Lakehouse e seu **SQL analytics endpoint** são itens diferentes desse destino. Não usar Warehouse de outro projeto. Se não existir um Warehouse do Fuel Watch BR, usar **New item → Warehouse**, nome sugerido **wh_fuelwatch**, no workspace com trial. Confirmar o nome efetivo; não pressupomos que esse item já existe.
3. Abrir o Warehouse e **New SQL query**. Para cada arquivo da tabela abaixo, abrir o arquivo local, copiar **todo** seu conteúdo para uma consulta separada e selecionar **Run**. Não colar os nomes dos arquivos e não recortar `CREATE VIEW`: a instalação já separa esses batches internamente.

| Ordem/arquivo em `warehouse/` | Resultado esperado |
| --- | --- |
| `00_preflight.sql` | Nome do item correto e `Latin1_General_100_BIN2_UTF8`; erro de collation interrompe o roteiro |
| `01_lab_setup.sql` | `m04_lab_setup_ready`; somente objetos no schema `lab_m04` |
| `02_lab_seed.sql` | `m04_reference_ready`, 181 dias e 92 municípios; pode repetir sem duplicar o seed completo |
| `03_lab_fixture_suite.sql` | `m04_fixture_suite_validated`, `experiment_id`, **7 cenários verificados**, mais tabela detalhada |
| `04_lab_reconcile.sql` | Todos os checks `errors=0`; 4 coletas/1 posto/1 município, zero incomuns; contagem e soma semanal iguais às da fato |

O arquivo 03 executa os cenários em sequência e trata apenas as duas falhas esperadas. Qualquer erro diferente interrompe a consulta. Sua última ação restaura o stage aprovado após a falha injetada, sem publicar de novo.

| Cenário | Estado publicado esperado |
| --- | --- |
| Base | 4 fatos; 2 versões observadas de posto |
| Repetição | Mesmo estado, sem versões extras |
| Atributo atrasado em 08/01 | 5 fatos; 4 versões, com intervalos recalculados |
| Correção de atributo | 4 fatos; 1 versão; transição corrigida desaparece |
| Correção apenas de preço | 4 fatos; 2 versões; preço 7.000 em 05/01 |
| Conflito | Erro **51006** capturado; publicação de preço 7.000 preservada |
| Falha após escritas | Erro **51999** capturado após inserir fatos/dimensões; rollback deve restaurar integralmente a publicação anterior |

As comparações verificam valores e intervalos completos, não apenas quantidades. O erro 51999 é proposital dentro do procedimento e capturado pelo teste; a consulta completa deve terminar com status verde. Uma consulta vermelha não é o sucesso esperado do laboratório. `lab_m04.fixture_checks` conserva resultados por `experiment_id`; uma repetição cria outro experimento.

**Guardar:** nome do Warehouse e collation, resultado completo do arquivo 03 e todos os result sets do 04, com data/horário e versão do pacote. Pode copiar como texto ou exportar os resultados do SQL query editor. Depois de cada execução conservar sua evidência; não sobrescrever a única cópia anterior. Enviar o resultado `m04_fixture_suite_validated` inteiro para conferirmos.

## B — Exportar o snapshot oficial com notebook 07

1. Abrir **lh_fuelwatch → Files** e criar **m04_input**.
2. Enviar somente os seis arquivos abaixo, diretamente da pasta local `data/artifacts/m04_fabric/upload/` para `Files/m04_input/`, sem subpasta adicional e sem extrair o ZIP:

| Arquivo | Conteúdo |
| --- | --- |
| `manifest.json` | Hashes e versões aprovadas de todos os insumos |
| `fuelwatch_rules.zip` | Regras M02 preservadas, usadas na comparação Spark |
| `reference.parquet` | Os 13 campos das 8.052 coletas aprovadas |
| `municipios-rj.http.gz` | Bytes oficiais IBGE preservados por hash |
| `expected_history.parquet` | Oracle local: 518 versões observadas |
| `expected_weekly.parquet` | Oracle local: 656 grupos semanais |

3. Importar `notebooks/07_export_gold_input.ipynb` pelo workspace. Anexar **lh_fuelwatch** e defini-lo como **default Lakehouse**. Usar sessão nova; os parâmetros já estão preenchidos com caminho e hash do pacote.
4. Selecionar **Run all**. O notebook procura recibos bem-sucedidos em `Files/audit/m03_official/*/summary.json`, aceita somente o contrato que corresponda ao snapshot ativo e fixa sua versão Delta explicitamente. Confere identidade, hashes, contrato, estado atual e os 13 campos antes de exportar. Não modifica nenhuma tabela Silver, Bronze, referência IBGE ou `lab_m03_*`.
5. Aguardar o JSON **m04_transfer_ready**, guardar o retorno completo e usar **Stop session**. O retorno contém `batch_id`; copiar seu valor para a etapa C.

Exemplo de formato, sem substituir o JSON real:

```json
{"status":"m04_transfer_ready","batch_id":"<UUID real da execução>","source_table":"silver_preco_publicado","source_delta_version":"<versão real do consumer_contract>","snapshot_id":"<snapshot real M03>","coletas":8052,"stations":502,"municipalities":27,"unusual_prices":26,"silver_unchanged":true}
```

As tabelas `m04_transfer_coletas`, `m04_transfer_municipios`, `m04_transfer_calendar`, `m04_transfer_expected_posto` e `m04_transfer_expected_weekly` recebem linhas identificadas pelo mesmo lote. `m04_transfer_manifest` é gravada por último, após conferir cada gravação. Tentativa incompleta não ganha esse manifesto pronto. A auditoria fica em `Files/audit/m04/<batch_id>/transfer.json`.

Novo Run all gera outro `batch_id`; nunca combinar partes de lotes diferentes. A preservação dos lotes é por append e convenção operacional, não por armazenamento WORM ou segurança já exercitada. Não executar duas instâncias em paralelo.

## C — Carregar e validar Gold oficial

1. Voltar ao Warehouse do Fuel Watch BR, **New SQL query**. Executar `20_gold_setup.sql` integralmente; esperar **m04_gold_setup_ready**. Ele cria o schema **gold** e seus objetos. Não modifica o schema do laboratório.
2. No Explorer do Warehouse, adicionar o **SQL analytics endpoint** de `lh_fuelwatch`, no mesmo workspace, por **+ Warehouses** quando essa ação estiver disponível. Confirmar o nome de banco e schema em que as tabelas `m04_transfer_*` aparecem. O padrão dos scripts é banco `lh_fuelwatch`, schema `dbo`; se o nome efetivo for outro, usar o valor mostrado no Explorer.
3. Abrir `30_import_approved_snapshot.sql`. Alterar somente os valores das três variáveis no início: `@lakehouse`, `@lakehouse_schema` e `@batch_id`. O terceiro recebe o UUID real do notebook 07. Manter o restante do script.
4. Executar o arquivo 30 inteiro. Ele exige um manifesto pronto do lote, todos os volumes, hashes e versão aprovados, e copia o snapshot para o stage da Gold. A transferência é comparada por valores, incluindo textos como bytes para conservar acentos e espaços. Esperar **m04_stage_ready** com `is_synthetic=false`.
5. Executar `31_publish_approved_snapshot.sql` inteiro. Não há parâmetro para editar: o procedimento lê o batch do stage, valida e publica dimensões/fatos/seleção na transação Warehouse. Esperar **gold_published**.
6. Executar `32_gold_validate.sql` inteiro. Ele compara fatos com o stage aprovado, todo o histórico com o oracle local e os grupos semanais com suas expectativas; verifica calendário e associação temporal. Esperar um JSON **m04_gold_snapshot_validated**, com os números abaixo.
7. Repetir **31 e 32**, com o mesmo stage. Os mesmos valores e multiplicidades devem continuar aprovados; `published_at_utc` pode mudar. Isso verifica repetição de negócio, não ausência de escrita física.

| Métrica no resultado real | Esperado neste baseline |
| --- | --- |
| `observations` | 8.052 |
| `stations` | 502 |
| `municipalities` | 27 |
| `unusual_prices` | 26 |
| `station_versions` | 518 |
| `weekly_groups` | 656 |
| `business_columns_compared` | 13 |
| `full_row_comparison_passed` | true |
| Soma de preços, fato/semanal | 52.777,200 em ambos |

O script 32 falha antes de emitir o JSON verde se houver divergência. Guardar os retornos completos das duas publicações/validações e o JSON do notebook 07. A publicação conserva tabela de origem, versão Delta, snapshot_id e hashes do M03. Não marcar M04 concluído apenas porque o setup ou a carga terminou sem erro.

## Erros e retomada

| Sinal | Próxima ação |
| --- | --- |
| DDL/DML não permitido | Conferir se abriu **Warehouse**; SQL analytics endpoint do Lakehouse não é o destino das escritas |
| Collation diferente | Guardar resultado do preflight e revisar compatibilidade; não remover o guard nem criar recurso pago para contornar |
| HTTP 430 no notebook | Conferir sessões e Monitoring hub, parar sessão anterior e tentar serialmente; não ampliar capacidade paga |
| Silver mudou / hash ou comparação divergiu | Guardar erro; revisar o snapshot aprovado e gerar pacote novo conscientemente; não editar versão/hash no notebook |
| Nenhum consumer_contract válido ou tabela silver_preco_publicado ausente | Concluir a seleção oficial do notebook 06 e conferir seu summary.json no Lakehouse padrão; não usar a fixture do notebook 05 como substituto |
| Tabela `m04_transfer_*` ausente no Explorer/consulta | Conferir nome do banco/schema. No SQL analytics endpoint, usar **Refresh** e aguardar a sincronização; só continuar quando o lote estiver visível |
| Erro 51201 ou 51203 | Manifesto/tabelas ainda não estão completos no endpoint, ou batch incorreto. Conferir UUID, atualizar metadata e repetir **30**; não executar **31** antes de `m04_stage_ready` |
| Falha antes do manifesto no notebook | Lote parcial fica preservado para diagnóstico; novo Run all cria outro lote. Usar somente o UUID de uma execução `m04_transfer_ready` |
| Arquivo 03 interrompido | Guardar erro e experiment_id quando disponível. Resultados já aprovados permanecem em `fixture_checks`; depois de corrigir a causa, reexecutar a suíte inteira, sem apagar tabelas oficiais |
| Falha na publicação oficial | Guardar erro e batch. A transação do procedimento deve preservar a publicação anterior; confirmar dados antes de alegar rollback. Corrigir a causa e repetir 31/32 com o stage aprovado |

Se houver uma compilação T-SQL incompatível no ambiente, parar no arquivo correspondente e enviar a mensagem completa. Os testes locais não substituem essa verificação; não existe garantia antecipada de compatibilidade runtime.

O carregamento de referências e stage do arquivo 30 é uma transação separada da publicação do 31. Neste pacote, calendário/IBGE são fixos e verificados, de modo que reimportá-los não muda seu significado. Não usar esse mecanismo para trocar referência municipal ou misturar outros escopos. A orquestração e recuperação geral entre camadas pertencem ao M05.

## Evidência e aceite

Criar um registro por execução, associado ao pacote/commit. Enviar os JSONs reais para armazenarmos em `evidence/fabric/gold/` com proveniência; o agente não está consultando tabelas remotamente neste roteiro.

| Critério M04 | Evidência necessária |
| --- | --- |
| Modelo dimensional real | Setup e leitura dos objetos `gold` no Warehouse |
| Reconciliação completa | JSON final, 8.052 fatos, 13 campos, chaves/referências corretas |
| SCD2 observado | Sete testes sintéticos, intervalos e referências temporais íntegros; histórico real igual ao oracle |
| Atraso/correção/repetição | Suíte sintética aprovada, rollback observado e 31/32 repetidos sem alteração de negócio |
| Semana ISO e agregação | 656 grupos reconciliados integralmente, calendário válido e soma/quantidade corretas |

O M04 foi aceito pelos resultados reais registrados: lote 4ef52958, duas validações completas sem diferenças e sete cenários Warehouse. O estado dos demais marcos segue suas próprias evidências; o aceite M04 não comprova orquestração, segurança ou implantação. Em uma reprodução, exigir novamente o recibo oficial do notebook 06.

## Regerar localmente, somente antes de iniciar a execução

```powershell
python -m scripts.prepare_m04_gold
python -m scripts.build_m04_bundle
python -m unittest discover -s tests -v
```

Não regenerar nem misturar arquivos durante sua execução: manifestos e notebook precisam pertencer ao mesmo pacote. Após upload, conservar os arquivos aprovados até fechar a etapa.

Referências consultadas: [consultas entre bancos no mesmo workspace](https://learn.microsoft.com/en-us/fabric/data-warehouse/query-warehouse), [sincronização do SQL analytics endpoint](https://learn.microsoft.com/en-us/fabric/data-engineering/sql-analytics-endpoint-metadata-sync), [transações Warehouse](https://learn.microsoft.com/en-us/fabric/data-warehouse/transactions) e [superfície T-SQL](https://learn.microsoft.com/en-us/fabric/data-warehouse/tsql-surface-area).
