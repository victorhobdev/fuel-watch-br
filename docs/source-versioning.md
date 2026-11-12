# M03 — Versões, correções antigas e backfill

Estado: **laboratório do notebook 05 validado no Fabric; integração oficial pendente**. Os 17 cenários passaram conforme a saída recebida e as [27 verificações locais dessa evidência](../evidence/fabric/versioning/README.md). O M02 e sua Silver permanecem preservados. O [guia do notebook 05](m03-fabric.md) permite reproduzir o laboratório.

**Próxima execução entregue:** [notebook 06 — seleção oficial e repetição](m03-official.md). Reutiliza `Files/m02_input`, reconcilia os bytes oficiais com a Bronze, seleciona o snapshot revisado e fornece o contrato de consumo Gold. O marco será fechado somente após conferir seu retorno Fabric.

## Por que comparar versões completas

Um filtro `data_coleta > MAX(data_coleta)` perde correções e chegadas atrasadas. O laboratório começa com junho já presente e muda janeiro: a data máxima continua igual, mas o estado de negócio precisa mudar.

Um novo SHA-256 identifica bytes diferentes, não necessariamente novas coletas. Uma duplicata exata ou uma alteração de ordenação pode mudar o arquivo sem mudar o negócio. Comparamos a chave `cnpj + produto + data_coleta + unidade` e os 12 campos tipados de origem; a classificação IQR é derivada e será recalculada sobre o escopo aceito na implementação Silver. Não agregamos semanas neste marco.

## Contrato do laboratório

- Fonte `lab_anp_synthetic`, `is_synthetic=true` e escopo `lab_m03_2026_1_rj_gasolina`. CNPJs, revendas, bandeiras e preços são inventados. O código recusa escopos oficiais.
- CSV com os mesmos 16 nomes de coluna da ANP, UTF-8 BOM, separador `;`, datas brasileiras e decimal com vírgula. Cada tentativa preserva seus bytes e manifesto.
- Manifesto contém fonte, escopo/período/versão do contrato, SHA-256, `complete_snapshot`, `supersedes_sha256` e diferenças esperadas (`inserted`, `removed`, `updated`).
- A versão candidata precisa ter hash, layout, regras de qualidade e chave válidos. Conflitos não recebem vencedor arbitrário. Duplicatas exatas são contabilizadas sem criar novas coletas. Preço incomum positivo continua válido conforme o contrato.
- `complete_snapshot=true` é uma declaração, não prova de completude. Remoções ficam bloqueadas se o delta não tiver sido revisado. Neste laboratório as diferenças esperadas são fixtures automatizados vinculados aos bytes; não representam aprovação externa ou autorização para apagar dados oficiais.
- A candidata informa qual hash ativo espera substituir. Uma seleção baseada em versão anterior é rejeitada. Isso modela uma execução serial; não demonstra controle de concorrência entre jobs Fabric.
- Rejeição gera auditoria e preserva a seleção ativa. Os arquivos históricos permanecem preservados. Uma repetição gera novo run, mantendo as coletas e a seleção ativa.

## Executar e verificar localmente

Na raiz do projeto, sem instalar dependências adicionais:

```powershell
python -m unittest tests.test_versioning_lab -v
python -m scripts.prepare_m03_lab
```

O segundo comando cria uma pasta nova `data/artifacts/m03/<run_id>/`, fora do Git. Cada tentativa guarda CSV, manifesto, auditoria e seleção ativa antes/depois. O resumo rastreável fica em `evidence/m03/local-lab.json`. O modelo de referência é `fuelwatch/versioning_lab.py`; não grava tabelas Delta ou dados oficiais.

| Cenário | Resultado esperado |
| --- | --- |
| Base | Quatro coletas aceitas |
| Repetição da base | Zero diferenças; seleção ativa idêntica |
| Correção em 05/01 | Uma atualização, três registros intactos; junho preservado |
| Chegada de 08/01 | Uma inclusão; datas anteriores não limitam ingestão |
| Remoção explícita de 12/01 | Uma remoção no snapshot completo aprovado |
| Duplicata exata | Cinco linhas físicas, quatro coletas; mesmo negócio |
| Conflito de chave | Rejeição com registros conflitantes na auditoria |
| Preço negativo | Rejeição com quarentena rastreável |
| Arquivo vazio | Rejeição; não esvazia o escopo ativo |
| Snapshot parcial | Rejeição antes da substituição |
| Remoção sem delta aprovado | Rejeição mesmo com declaração de completude |
| Base antiga reenviada | Rejeição por seleção desatualizada |
| SHA errado e layout inválido | Duas rejeições estruturais |
| Retry com SHA correto | Aceite dos bytes válidos preservando o negócio |

São 15 tentativas no roteiro. Todas verificam um segundo escopo sentinela, que deve permanecer idêntico. Os testes também verificam divergência de escopo e recusa de escopo oficial.

## Próximo bloco no Fabric, após aceitar M02

1. Pré-requisito concluído: primeira Silver e repetição sem diferenças registradas, com 8.052 coletas, 502 postos e 27 municípios. O notebook 05 também confere o baseline antes de começar.
2. Importar o notebook 05 entregue e enviar o pacote M03 conforme o guia. Ele cria tabelas com prefixo `lab_m03_`, sem alterar `silver_preco_coletado`, preserva as entradas e executa 17 tentativas. A evidência de preparação fica em `evidence/m03/notebook-preparation.json`.
3. Definir o catálogo de entregas/tentativas e a seleção de versão por escopo. Separar tentativa recebida, candidata validada, candidata rejeitada e versão ativa. Uma versão já vista pode receber novas tentativas; seu SHA não define sozinho o estado da tentativa.
4. Materializar a candidata antes da promoção. Reconciliar tipos, categorias de qualidade e diferenças completas de registros com a versão ativa. Guardar as chaves e valores antes/depois, não apenas contagens ou fingerprints.
5. Executar os cinco cenários de aceite do roadmap em Spark/Delta: repetição, correção antiga, atraso, remoção e conflito. Conferir também snapshot parcial, retry e proteção de outro escopo. Usar execução serial até demonstrar um mecanismo seguro de promoção concorrente.
6. Testar falha antes da promoção e recuperação. Só depois escolher o mecanismo de publicação real: escrita por versão e seleção ativa, ou substituição atômica de escopo em uma tabela. Validar a atomicidade que o mecanismo escolhido realmente oferece; não presumir transação entre várias tabelas.
7. Integrar a estratégia ao fluxo oficial preservando a referência M02. Mudanças no notebook 04 exigirão nova versão explícita do pacote e repetição dos checks; não serão feitas durante sua execução atual.

Backfill significa reprocessar um escopo/período explicitamente selecionado a partir de versões preservadas. Não significa baixar apenas datas novas nem substituir automaticamente uma versão ativa por qualquer arquivo de URL conhecida. Uma republicação oficial real deve ser observada e identificada como tal; fixtures não provam que a ANP republicou esse semestre.

## Aceite e limites

Os cenários do laboratório e seus commits Delta foram validados pela saída Fabric recebida; não houve consulta remota independente. O M03 permanece em andamento para integrar o controle ao fluxo oficial: o notebook atual declara `official_integration_implemented=false`. A falha exercitada é uma exceção Python antes da promoção, sem demonstrar recuperação de perda de cluster ou atomicidade entre tabelas. Nenhum recurso pago foi criado por este trabalho.
