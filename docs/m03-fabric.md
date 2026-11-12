# Executar o M03 no Fabric — notebook 05

**Estado: entregue para execução; Spark/Delta ainda não validados neste notebook.** M02 já foi aceito pelas auditorias recebidas: 8.052 coletas, 502 postos, 27 municípios e repetição Silver sem diferenças. O notebook 03 é do M02/IBGE; este marco M03 usa o **notebook 05**.

## Arquivos e upload

Na pasta local `data/artifacts/m03_fabric/` há exatamente três arquivos para enviar:

| Arquivo | Função |
| --- | --- |
| `fuelwatch_rules.zip` | Contrato Python e transformação PySpark já usados no M02; manter como ZIP |
| `scenarios.json` | Bytes dos CSVs sintéticos, manifestos e expectativas dos 17 cenários |
| `manifest.json` | Tamanhos e hashes aprovados dos outros dois arquivos |

1. Com a sessão do 04 parada, abrir o Lakehouse **lh_fuelwatch** no workspace do projeto.
2. Em **Files**, criar a pasta **m03_input**.
3. Enviar os três arquivos diretamente para essa pasta, sem extrair o ZIP. O resultado deve ser `Files/m03_input/manifest.json`, sem outra pasta intermediária.
4. No workspace, usar a importação de notebook e selecionar **notebooks/05_source_versions_backfill.ipynb**.
5. Abrir o notebook 05, anexar **lh_fuelwatch** e defini-lo como **default Lakehouse**. Iniciar sessão nova; não reutilizar uma sessão com outra versão do pacote Python carregada.
6. Manter os dois parâmetros gerados: caminho `/lakehouse/default/Files/m03_input` e hash esperado do manifesto. Não trocar o hash para contornar erro de upload.
7. Selecionar **Run all**. Não executar outra instância em paralelo. Não é necessário instalar bibliotecas ou criar capacidade, pipeline ou Warehouse.

O bootstrap confere o manifesto e todos os arquivos antes de distribuir o ZIP para o Spark. A primeira ação do laboratório fixa a versão Delta da Silver oficial e reconcilia seu escopo, hashes e cobertura com M02. Depois começam as escritas sintéticas.

## O que observar durante a execução

Cada cenário concluído imprime `event=m03_scenario_verified`, com nome, status, diferenças e versões Delta antes/depois. O ensaio é pequeno em dados, mas envolve vários jobs e commits: aguardar a célula terminar.

| Tentativa | Esperado |
| --- | --- |
| `base` | Publica quatro coletas |
| `replay_base` | Mantém negócio, hash ativo e versão Delta |
| `correction_january` | Atualiza uma coleta de janeiro; junho já existe e permanece igual |
| `late_arrival` | Inclui uma coleta atrasada de janeiro |
| `removed_row` | Remove exatamente uma coleta em snapshot completo com delta esperado |
| `exact_duplicate` | Cinco linhas físicas, quatro coletas; bytes novos, negócio igual |
| `conflict`, `invalid`, `empty` | Três rejeições com estado ativo preservado |
| `partial`, `unapproved_removal` | Rejeita snapshot declarado parcial e remoção sem delta revisado |
| `stale_base`, `bad_hash`, `bad_layout` | Rejeita seleção antiga, hash incorreto e cabeçalho inválido |
| `retry_correct_hash` | Aceita os bytes válidos, sem acrescentar coletas |
| `fail_before_promotion` | Persiste a candidata e injeta uma exceção Python antes da promoção; estado ativo não muda |
| `retry_after_failure` | Reprocessa os mesmos bytes e promove uma atualização; sem duplicação |

A falha injetada é capturada pelo notebook e **não deve deixar a célula vermelha**. Um erro inesperado interrompe a célula; não interpretar isso como parte do teste.

O preço de 05/01 começa em 6,100, é corrigido para 6,350 e termina em 6,400 após a recuperação. A data máxima continua 30/06/2026. Os 12 campos de origem determinam inclusões/alterações/remoções; o sinal IQR é recalculado na candidata e também entra na comparação integral do estado publicado.

## Tabelas e evidências

- **lab_m03_active:** coletas publicadas e identificação da versão ativa na mesma tabela Delta. Cada promoção substitui somente `experiment_id + scope_id`; a versão e as coletas avançam no mesmo commit.
- **lab_m03_versions:** histórico das candidatas materializadas, inclusive a candidata deixada pela falha controlada.
- **lab_m03_attempts:** uma auditoria por tentativa, com manifesto, diagnósticos, status, comparação de registros e referências às versões Delta. Registros inválidos/conflitantes incluem payload e motivos no JSON de auditoria.

Um segundo escopo sintético é conferido integralmente a cada tentativa. As tabelas são particionadas por experimento apenas para separar estes pequenos ensaios; isso não é recomendação de particionamento para produção. O notebook usa quatro partições de shuffle na sessão dedicada por causa da fixture minúscula.

Cada **Run all** cria um `experiment_id` novo e preserva os ensaios anteriores. A repetição do mesmo arquivo é verificada **dentro** do ensaio. Não confundir a contagem total das tabelas com a contagem do experimento atual.

Arquivos preservados:

- `Files/lab_m03/landing/<experiment_id>/<attempt_id>/`: CSV e manifesto de cada entrega.
- `Files/audit/m03/<experiment_id>/<ordem>_<cenario>/`: auditoria recebida/final, estado antes/depois e checkpoint da candidata quando existente.
- `Files/audit/m03/<experiment_id>/summary.json`: resultado final; `progress.json` registra os cenários concluídos.

## Resultado para enviar

O último JSON deve conter:

```json
{
  "status": "m03_lab_validated",
  "environment": "fabric",
  "is_synthetic": true,
  "scenarios_verified": 17,
  "final_rows": 4,
  "attempt_status_counts": {
    "published": 7,
    "replayed": 1,
    "rejected": 8,
    "failed_before_promotion": 1
  },
  "candidate_snapshots": 8,
  "injected_failure_recovered": true,
  "official_silver_unchanged": true,
  "official_integration_implemented": false
}
```

Esses são os **valores esperados**, não uma execução já realizada. O JSON real inclui IDs, horários UTC, runtime, hashes e versões Delta. Copiar o JSON final inteiro para registrar as evidências; parar a sessão depois de concluir.

## Em caso de erro

Guardar a mensagem completa e o `experiment_id`, se já tiver sido impresso/gravado. Não alterar hashes, apagar tabelas ou editar a Silver oficial para forçar aceite. Para HTTP 430, conferir sessões retidas e a fila antes de tentar novamente; não ampliar capacidade paga. Se a sessão parou no meio, os arquivos de auditoria já gravados e candidatas permanecem para diagnóstico. Novo Run all inicia outro experimento, não retoma silenciosamente um experimento incompleto.

Uma falha depois do commit pode deixar publicação existente com auditoria incompleta. Não há transação entre active, versions, attempts e arquivos; investigar o histórico antes de declarar rollback. A recuperação exercitada aqui é uma exceção Python **antes** do commit ativo; não simula perda do cluster nem falha durante o commit.

O sucesso valida o laboratório sintético em execução serial. Integração da seleção de versões ao fluxo oficial e garantias entre jobs concorrentes continuam pendentes. Nenhuma republicação real da ANP é reivindicada.

## Referências verificadas

- [Microsoft — leitura/escrita no Lakehouse por notebook](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-notebook-load-data): mount padrão, caminhos Files e tabelas Delta.
- [Delta Lake — batch, time travel e replaceWhere](https://docs.delta.io/delta-batch/): snapshots fixos e substituição atômica por predicado em uma tabela.
