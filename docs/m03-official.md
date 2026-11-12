# Fechar M03 — seleção oficial no notebook 06

**Estado: código entregue e verificado localmente; execução Fabric pendente.** O notebook 05 já demonstrou correção antiga, atraso, remoção, rejeição e recuperação com dados sintéticos. Agora falta registrar a versão **oficial aprovada**, repetir sua seleção e definir o contrato de entrada do Gold.

## Executar

1. Parar a sessão do notebook 05.
2. Importar `notebooks/06_official_source_selection.ipynb` no workspace do projeto.
3. Anexar **lh_fuelwatch** como **default Lakehouse** e usar uma sessão nova.
4. Manter os parâmetros preenchidos e selecionar **Run all**. Não executar outro publicador ou os notebooks 01/03/04 em paralelo.
5. Enviar o JSON final inteiro. Depois de concluir, parar a sessão.

**Não há novo upload de dados.** São reutilizados os quatro arquivos que já estão em `Files/m02_input`. O bootstrap confere seus hashes. Se a pasta foi removida, restaurar os arquivos aprovados de `data/artifacts/m02`, mantendo o ZIP fechado. Os dados oficiais preservados pelo notebook 01 também devem continuar em `Files/raw/anp_2026_1/<hash>/ca-2026-01.zip` e `Files/extracted/anp_2026_1/<hash>/source.csv`.

## O que será demonstrado

- ZIP e CSV preservados continuam com os hashes revisados; cabeçalho, quantidade de campos e 422.418 registros são conferidos.
- CSV e Bronze coincidem nas 16 colunas, inclusive multiplicidade. Isso vincula a transformação aos bytes recebidos, além de conferir somente contagens.
- Referência IBGE, tipagem, qualidade, IQR e 13 campos de negócio coincidem com o baseline aceito: 8.052 coletas, 502 postos, 27 municípios e 26 sinais de preço incomum.
- A política registra fonte, hash, referência IBGE, escopo, contrato, snapshot completo, identidade anterior esperada e delta revisado. Uma seleção diferente da esperada bloqueia publicação; nenhuma remoção fica autorizada apenas por declarar completude.
- A primeira tentativa materializa uma versão e seleciona as coletas oficiais. A segunda gera auditoria nova, verifica o mesmo negócio e não escreve outra versão na seleção ativa.
- A seleção mantém os dados e a identidade da versão no mesmo commit Delta de uma tabela. Bronze, referência IBGE, Silver M02 e tabelas do laboratório não são alvos de escrita.

## Saídas e consumo Gold

| Tabela | Finalidade |
| --- | --- |
| `silver_preco_versionado` | Candidatas oficiais materializadas com snapshot_id, hashes e política |
| `silver_preco_publicado` | Coletas da versão selecionada por scope_id; fonte de entrada do próximo bloco Gold |
| `anp_publication_attempts` | Tentativas com status, decisões e auditoria JSON |

O `consumer_contract` do resultado informa tabela, versão Delta, escopo, hashes e snapshot_id. O consumidor fixa essa versão Delta, filtra o escopo e reconcilia a identidade antes da carga Gold. A execução de Gold pertence ao M04; não é necessária para validar a seleção no M03.

Auditorias: `Files/audit/m03_official/<run_id>/`. Incluem o manifesto da política, vínculo com os arquivos oficiais, diferenças de registros nas publicações, checkpoints de candidatas e `summary.json`.

## Aceite para fechar o marco

Valores esperados no resumo:

```json
{
  "status": "m03_official_selection_validated",
  "official_integration_implemented": true,
  "silver_rows": 8052,
  "stations": 502,
  "municipalities": 27,
  "unusual_iqr_rows": 26,
  "replay_without_active_commit": true,
  "m02_inputs_unchanged": true
}
```

Na primeira execução, `registration.status` deve ser `published` e `replay.status`, `replayed`. Se já existir a mesma seleção, ambos podem ser `replayed`; uma seleção diferente deve ser investigada. O JSON também precisa conter a comparação integral CSV/Bronze e o contrato de consumo com snapshot/versionamento identificados.

Com esse retorno conferido, o M03 poderá ser fechado junto da evidência dos 17 cenários do notebook 05. Até recebê-lo, registrar somente **preparado**, sem marcar o marco como concluído.

## Limites e recuperação

Este notebook registra o semestre e os hashes já revisados; não consulta a URL por uma suposta versão mais nova nem afirma uma republicação real. Correções de negócio foram exercitadas no laboratório. Outro arquivo oficial exige perfil, referência e política próprios revisados; não trocar um hash isolado para forçar aceite. Agendamento, descoberta de mudanças e orquestração serão tratados no M05.

Não há transação entre histórico, tabela publicada, auditoria e arquivos. Falha depois do commit exige inspecionar a versão e os checkpoints antes de declarar rollback; nova execução da mesma entrada compara a seleção existente. O controle exige execução serial e não demonstra exclusão mútua entre jobs. Em erro, enviar mensagem completa e run_id; não apagar tabelas ou aumentar capacidade paga.

Referências: [Microsoft — Lakehouse em notebooks](https://learn.microsoft.com/en-us/fabric/data-engineering/lakehouse-notebook-load-data) e [Delta Lake — batch, time travel e replaceWhere](https://docs.delta.io/delta-batch/).
