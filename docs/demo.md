# Demonstrações reproduzíveis

Usar primeiro os registros existentes. Não disparar novamente cargas só para abrir seus resultados. Os IDs abaixo são execuções reais, não fixtures de documentação.

## 1 — carga válida

Abrir `evidence/fabric/orchestration/pipeline-runs/3ceb55a5-8026-4950-97fb-c2eb229d6c1d/verification.json`. Relacionar Copy → Bronze 422.418 → Silver 8.052 → export batch → Gold. Conferir 502 postos, 27 municípios, 518 versões observadas, 656 grupos e soma 52.777,200. A origem é o hash ANP aprovado; o snapshot IBGE e a versão Delta selecionada estão nos receipts filhos.

Mostrar que a fato mantém a coleta; a semana é derivada. Explicar SCD2 como intervalo de mudança observada, sem inferir a data jurídica de uma troca de bandeira. O commit de consolidação `e373d1e` contém o código/índice revisado; os receipts preservam hashes/definições observadas na execução, sem afirmar que cada run foi iniciado por GitHub Actions.

## 2 — repetição

Comparar o baseline com `bc036008-ccea-404e-9362-ce9dc081db6b`. Os seis fingerprints de negócio são iguais, mas a execução/auditoria/lote têm identidades próprias. Na importação houve uma falha por sincronização do SQL endpoint e sucesso com mesmo comando/lote após retry finito. Nenhuma contagem de negócio cresce por repetir a mesma versão.

Não usar somente COUNT para essa prova: mostrar a comparação integral de campos e os hashes derivados da projeção completa. Novo commit Delta ou novo batch não significa mudança de preço.

## 3 — falha e recuperação

Abrir `4145ce90-e750-4109-a0c7-4637ba50a209`: falha intencional Gold depois do INSERT e antes do COMMIT. A API encapsula o erro como 2011; a evidência da posição do THROW 51999 vem da definição real da procedure, não de um número inventado na resposta. Guards mostram publicação anterior preservada.

Abrir a recuperação `dc94cb54-4930-427f-9e08-6ea8b4996747` e comparar negócio com o baseline. Para bloqueio antes de Gold, usar a falha Silver `b9812604-df3d-4705-bc30-5324be35779d` e recuperação `5c9a3991-61b9-454a-a686-2a96c2c04c17`.

## Consumo e tempo real

No relatório Power BI, mostrar evolução semanal, comparação municipal e cobertura. A [conferência DAX/SQL](../evidence/fabric/consumption/measure-verification-2026-11-13.json) cobre cinco medidas em quatro recortes; não somar postos semanais nem tirar média simples de médias municipais.

No M10, mostrar o manifesto do lote `daf2320c-b0bc-4eef-b908-a2dd80939088`, quatro consultas, 1.000 IDs reconciliados, vinte reinjeções e dez eventos atrasados. O MCP Activator confirmou uma ativação e o pipeline de auditoria terminou no run `17476695-2e1c-42ab-a7db-6734d24a73d3`. O scheduler rotulou esse job `Manual`, portanto esse campo isolado não prova sua origem: cruzar a ação configurada, o histórico de ativação e a ausência de POST manual de início. A regra está desligada e os destinos pausados.

## Limites a declarar

Não demonstramos concorrência entre publicadores nem uma transação única Lakehouse/Warehouse. O ensaio de desempenho mede uma agregação em cache; não comprova economia monetária ou aceleração do pipeline completo. O usuário dispensou a segunda conta e aceitou revisão de implementação M07; negação/RLS/DDM com leitor não foram testados. Integração Git nativa foi exercitada seletivamente no notebook 08, commit `6a30720`, além do push/CI. Não foi feito envio nativo de todos os itens.

## Fase 2 — observatório nacional e histórico

1. Abrir `evidence/phase2/deployment/rebuild-history-report-qa4.pdf`. A página Panorama traz a evolução semanal da mediana de posto; a página Postos e bandeiras limita o ranking aos 100 maiores desvios elegíveis; a terceira compara postos comuns entre semestres consecutivos; a quarta expõe os grupos populacionais e o status da cobertura climática.
2. Explicar o universo: 2.125.547 coletas ANP, 13.030 postos, 462 municípios, 27 UFs e seis produtos no histórico até junho de 2026. A observação individual continua no fato; semanas e comparações são derivados.
3. Ao discutir postos comuns, destacar que a comparação exige o mesmo CNPJ, produto, unidade, UF e município nos dois primeiros semestres. A amostra não é todos os postos existentes, preço é nominal e ausência de coleta não é zero.
4. Ao discutir contexto, informar que a população é referência retrospectiva de julho por município/ano; clima representa associação geográfica e elegibilidade horária. O relatório mostra cobertura e ausência; nenhuma relação causal foi inferida.
5. O Eventstream/Eventhouse usa apenas dados sintéticos. `evidence/phase2/streaming/activator-action.json` prova uma ativação real e a conclusão do pipeline interno no intervalo da sonda sintética de dois eventos. O registro Activator não expõe `event_id`; não afirmar vínculo individual com um dos eventos. A regra foi desligada e destinos pausados.
6. O rebuild limpo usou uma capacidade FTL4 trial já existente. `evidence/phase2/deployment/resource-audit-2026-11-15.json` registra zero jobs, sessões Spark e agendas habilitadas nos workspaces dev, test e rebuild. Expiração da trial e consumo CU não foram verificados.

Desempenho: `evidence/phase2/performance/context-query.json` compara a consulta completa da view com a cópia materializada reconciliada. O resultado retornou 6.914 grupos sobre uma publicação de 2.125.547 coletas; a mediana caiu de 7,375 s para 0,105 s nesta leitura TDS. Isso não mede DAX, o pipeline inteiro ou custo monetário.
