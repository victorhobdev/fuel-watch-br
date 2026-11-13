# Roadmap do Fuel Watch BR — marcos verificáveis

Atualizado em **12/11/2026**, America/Sao_Paulo. Base do acompanhamento: M00–M03 aceitos no Fabric e M04 preparado para execução. Planejamento, testes locais e execução validada são identificados separadamente.

**Objetivo:** concluir um observatório explicável de preços de combustíveis no Microsoft Fabric, com fluxo batch confiável, segurança e implantação demonstradas, laboratório sintético de streaming e consumo mínimo.

**Arquitetura:** ANP → Copy HTTP/Binary → arquivos preservados e Bronze Delta → Silver PySpark → Gold dimensional no Warehouse/T-SQL. IBGE fornece referência municipal identificada por snapshot. Eventstream → Eventhouse/KQL → Activator será um laboratório separado com eventos sintéticos.

**Base de decisões:** [contrato mínimo](../../contrato-minimo.md), [ponto de retomada](../../retomada-2026-11-11.md), [evidências Fabric](../../../evidence/fabric/README.md) e instruções do usuário. O roteiro detalhado de interface está em [primeira execução Fabric](../../fabric-primeira-execucao.md).

## Como acompanhar

- **Estado atual: 4 de 12 marcos concluídos.** Isso conta entregas aceitas, não representa percentual de esforço ou de tempo.
- Cada marco tem cinco critérios de aceite. Marcar uma caixa exige uma evidência identificada: execução, consulta, comparação, matriz ou documento verificado.
- Código preparado, teste local e execução no Fabric são estados distintos. Uma etapa que depende de Fabric não fica concluída apenas por passar localmente.
- Evidências M00–M02 e laboratório M03 foram fornecidas pelo usuário e conferidas localmente. A seleção oficial M03 foi executada pelo agente na guia Fabric autorizada, com saída observada diretamente. A proveniência acompanha cada registro; não houve consulta independente fora dos notebooks.
- Para concluir um marco: fechar seus cinco critérios, registrar evidências, atualizar status/data/commit e indicar o próximo. Falha deixa o marco aberto e preserva a última etapa verde.
- Dependência indisponível recebe **BLOQUEADO**, com condição de desbloqueio. Recurso condicionado pode receber **NÃO APLICÁVEL**, com justificativa explícita; isso não significa funcionalidade praticada.
- Não há calendário contratado. Atualizar a previsão de blocos após executar M02 e medir o ritmo real. Registrar data exata de expiração e capacidade do trial; os 60 dias foram informados, não têm vencimento confirmado neste repositório.

| Marco | Entrega verificável | Estado | Depende de |
| --- | --- | --- | --- |
| M00 | Fontes, contrato e referência local | CONCLUÍDO | — |
| M01 | Ingestão e Bronze com repetição validada no Fabric | CONCLUÍDO | M00 |
| M02 | IBGE e Silver tipada/validada no Fabric | CONCLUÍDO | M01 |
| M03 | Versões de origem, correções antigas e backfill | CONCLUÍDO | M02 |
| M04 | Gold dimensional e histórico observado do posto | PREPARAÇÃO LOCAL | M03 para integração/execução Fabric |
| M05 | Pipeline mestre e recuperação entre camadas | PLANEJADO | M04 |
| M06 | Exercício delimitado de Dataflow Gen2 | PLANEJADO | M02 |
| M07 | Acessos e governança com testes reais | PLANEJADO | M04 |
| M08 | Git do workspace e implantação entre ambientes | PLANEJADO | M05; M06 para implantar esse item |
| M09 | Monitoramento, diagnóstico e desempenho medido | PLANEJADO | M05; repetir verificações após M08 |
| M10 | Streaming sintético, KQL e alerta | PLANEJADO | M05 e condições operacionais de M09 |
| M11 | Consumo mínimo e encerramento reproduzível | PLANEJADO | M06–M10 e núcleo batch |

**Ordem principal:** M00 → M01 → M02 → M03 → M04 → M05 → M08 → M09 → M10 → M11. Encaixar M06 depois de M02 e M07 depois de M04, antes do aceite final. Essa ordem é de execução; versionamento, auditoria e revisão de acessos começam antes dos seus marcos finais.

## Regras globais

- Escopo inicial de negócio: GASOLINA/RJ, 01/01 a 30/06/2026, moeda BRL e unidade litro. O ZIP bruto contém o semestre nacional, com outros produtos. Expandir o consumo exige novo perfil e ajuste do contrato.
- Preservar a coleta individual antes da agregação semanal. Chave inicial: CNPJ textual + produto + data da coleta + unidade, sujeita à validação em novas entregas.
- Sem segredos, dados pessoais de conta ou informações corporativas no Git. Credenciais ficam em armazenamento protegido e configurações de ambiente ficam separadas do código.
- Priorizar capacidade trial já disponível. Nenhum recurso pago ou consumo de crédito fica autorizado por este roadmap. Uma alternativa paga exige estimativa e autorização antes da criação.
- Não exigir ganho de performance, zero rejeições ou uma mudança real de bandeira como condição artificial de sucesso. Exigir medição, rastreabilidade e comportamento correto.
- Dados sintéticos de testes/streaming ficam identificados e separados dos oficiais. Não apresentar eventos gerados como streaming da ANP.
- Usar uma sessão Spark por vez no laboratório: concluir, guardar saída, **Stop session**, alternar notebook. O incidente HTTP 430 demonstrou a importância de gerir recursos; sua causa específica não foi confirmada.
- Trabalho no Fabric seguirá por orientações e arquivos. Não controlar o mouse sem novo pedido explícito.

## M00 — Fontes e contrato

**Resultado:** uma referência real e reproduzível para julgar as próximas camadas.

- [x] Entregas oficiais ANP, metadados e municípios RJ do IBGE preservadas com SHA-256, URL e manifesto.
- [x] Perfil do semestre: 422.418 registros, 16 colunas, seis produtos, tipos/formato/unidades e chaves candidatas registrados.
- [x] Fatia local tipada com 8.052 coletas, 502 postos e 27 municípios; correspondência municipal única nesse recorte.
- [x] Dez testes locais aprovados, incluindo correção antiga, conflitos, quarentena e recuperação de escrita, com fixtures sintéticos identificados.
- [x] Contrato documenta CNPJ textual, decimal/data, duplicatas versus conflitos e preço incomum separado de inválido.

**Evidências existentes:** `evidence/source-profile.json`, `evidence/local-slice.json`, `evidence/verification.json`, `evidence/tests-local.txt`, `docs/contrato-minimo.md`.

## M01 — Bronze real no Fabric

**Resultado:** transporte e carga Delta rastreáveis, com repetição demonstrada.

- [x] Acesso ao Fabric/Lakehouse operacional demonstrado pelas saídas Spark recebidas; avaliação de 60 dias informada pelo usuário.
- [x] Copy HTTP/Binary com sucesso informado e caminho de landing identificado na auditoria do notebook.
- [x] Bronze preserva as ocorrências e reconcilia 422.418 registros com o CSV; ZIP de 8.488.624 bytes e hashes de ZIP/CSV iguais ao perfil local.
- [x] Duas execuções documentadas, com run_ids distintos e a mesma entrada, sem crescimento da contagem da versão de origem.
- [x] Comparação completa Delta 0 → 1 nas 16 colunas: 422.418 linhas em cada versão, mesmo esquema, nenhum registro ausente ou adicional.

**Evidências existentes:** `evidence/fabric/bronze/`, `evidence/fabric/bronze_replay/anp_2026_1_primeira_repeticao/`, `evidence/fabric/bronze-validation.json`. O teste cobre a mesma versão de origem; não cobre republicação ou promoção entre camadas.

## M02 — Referência IBGE e Silver PySpark

**Resultado:** coletas válidas, tipadas e identificadas por município, prontas para consumo dimensional.

**Passos:** registrar runtime/SKU/região/expiração do trial; conferir o Lakehouse padrão; levar o snapshot IBGE preservado ao Fabric; selecionar explicitamente o hash ANP aprovado; portar as regras locais; executar e reconciliar. A referência IBGE local recebida veio com Content-Encoding gzip, que precisa ser tratado.

- [x] Snapshot IBGE rastreável no Fabric, com os 92 códigos municipais do RJ da referência atual, sem chaves normalizadas ambíguas; 27 nomes presentes na fatia com correspondência única.
- [x] Silver real com CNPJ string, data date e preço decimal(10,3); para os mesmos snapshots/contrato, reconciliar a referência local de 8.052 coletas, 502 postos e 27 municípios. Investigar qualquer diferença, sem ajustar os dados apenas para atingir a meta.
- [x] Contagens fecham: recebidos = fora do recorte + selecionados; selecionados = inválidos + duplicatas exatas excedentes + conflitos após deduplicação + aceitos.
- [x] Fixture inválido conserva original/motivo em quarentena; fixture extremo válido permanece aceito e sinalizado. Registrar o efeito do IQR e comparar com os 26 sinais locais sem transformar esse número em regra universal.
- [x] Segunda execução mantém o mesmo multiconjunto e valores de negócio da Silver; comparação integral com o Parquet local sem diferenças inexplicadas.

**Métrica de saída:** zero diferença inexplicada e 100% dos selecionados contabilizados. Não exigir zero rejeições em novas origens.

**Evidências existentes:** `notebooks/03_ibge_reference.ipynb`, `notebooks/04_bronze_to_silver.ipynb`, pacote aprovado e 14 testes locais em `evidence/m02/preparation.json`; execuções IBGE, primeira Silver e repetição em `evidence/m02/fabric/`, com proveniência dos retornos e conferências locais. Cinco de cinco critérios aceitos em 12/11/2026: Delta 0 → 1, `same_business_as_previous=true`, 8.052 coletas, 502 postos, 27 municípios e comparação integral sem diferenças. SKU/região/expiração exata do trial seguem como pendências operacionais, sem impedir o aceite dos cinco critérios de dados.

## M03 — Versões, correção histórica e backfill

**Resultado:** corrigir o passado e recuperar chegadas atrasadas sem depender de MAX(data_coleta).

**Passos:** definir escopo completo da entrega, estados de processamento e versão ativa; preservar duas versões; atualizar/reconstruir somente o escopo afetado; comparar resultado esperado e publicado. Usar cópias sintéticas identificadas do snapshot quando não houver republicação oficial observada.

- [x] Manifesto/controle no Fabric distingue entrega, hash, semestre, run_id, estado e versão selecionada; entrada idêntica e conteúdo alterado recebem tratamento distinto.
- [x] Repetir a mesma versão mantém o estado de negócio, com auditoria de nova execução e sem novas observações publicadas.
- [x] Uma correção de preço de janeiro atualiza exatamente o registro/escopo esperado mesmo com dados de junho já existentes.
- [x] Uma chegada atrasada e uma remoção explícita em uma nova versão completa produzem as diferenças esperadas; registros fora do escopo permanecem iguais. Arquivo parcial não pode ser interpretado como substituição completa.
- [x] Conflito de chave ou falha estrutural bloqueia a promoção da versão, preserva a versão ativa anterior e permite reprocessamento/backfill rastreável após correção.

**Métrica de saída:** cinco cenários de controle aprovados: repetição, correção antiga, chegada atrasada, remoção e rejeição de versão conflitante. Hash/contagens sozinhos não substituem a comparação de registros afetados e não afetados.

**Arquivos previstos:** `notebooks/05_source_versions_backfill.ipynb`, ajustes no notebook 04, `docs/source-versioning.md`, `evidence/fabric/versioning/`.

**Preparação em 12/11:** [notebook 05 e guia de execução](../../m03-fabric.md) entregues, pacote de três arquivos e 17 tentativas sintéticas incluindo falha antes da promoção/retry. São 28 testes locais aprovados e formato/sintaxe conferidos, conforme [evidência de preparação](../../../evidence/m03/notebook-preparation.json). Spark/Delta deste notebook ainda não foram executados; os cinco critérios Fabric permanecem abertos. O pacote M02 continua preservado.

**Execução em 12/11:** [laboratório Fabric validado](../../../evidence/fabric/versioning/README.md), experimento ccbdb9dc: 17 cenários, versões ativas 0 → 7, oito rejeições, falha antes da promoção recuperada e Silver oficial na versão 1 sem diferenças. Os cinco cenários de controle foram exercitados no laboratório sintético. No checkpoint do laboratório a integração oficial ainda estava pendente; esse retorno isolado não fechava o marco.

**Fechamento em 12/11:** [seleção oficial e repetição validadas](../../../evidence/fabric/versioning/official/README.md), run 6929bb98, 34 checks. Foram publicadas 8.052 coletas; repetição preservou Delta 0 e snapshot, com Bronze/IBGE/Silver M02 nas mesmas versões. Contrato de consumo para Gold registrado, sessão encerrada e cinco critérios aceitos em conjunto com o laboratório. Nenhuma republicação real da ANP ou concorrência entre publicadores é reivindicada.

## M04 — Warehouse Gold e SCD2

**Resultado:** modelo dimensional de coleta e agregação semanal derivada, com histórico observado coerente.

**Passos:** confirmar que o item é Warehouse independente, e não apenas SQL analytics endpoint; definir dimensões e vigências; carregar por T-SQL; associar fatos às versões; reconciliar com Silver. Investigar os 14 CNPJs com múltiplas bandeiras observados localmente antes de usar casos reais como evidência de SCD2.

- [ ] Warehouse contém dimensões de data, produto, município e posto, além da fato de preço coletado; granularidade e chaves documentadas, com unidade em toda comparação.
- [ ] Fato reconcilia integralmente com a Silver aprovada; zero chaves de fato duplicadas e zero referências dimensionais inválidas sem tratamento documentado.
- [ ] SCD2 com intervalos [início, fim), zero sobreposições e exatamente uma versão apropriada para cada fato; fixture demonstra mudança de bandeira/nome com significado de observação, não de data jurídica.
- [ ] Chegada atrasada/correção de atributo ajusta intervalos e associações dos fatos; repetição não abre versões extras. Comparação esperada versus obtida aprovada.
- [ ] Agregação semanal usa calendário ISO explicitado e reconcilia com a fato; apresenta número de coletas/postos e cobertura. Média ponderada pela quantidade de observações quando derivada de agregados, sem inventar ponderação por volume vendido.

**Métrica de saída:** diferenças de preço/contagem inexplicadas = 0; sobreposições SCD2 = 0; associações temporais ambíguas = 0.

**Arquivos previstos:** `sql/warehouse/01_schema.sql`, `02_station_history.sql`, `03_publish_gold.sql`, `04_reconcile.sql`, `docs/data-model.md`, `evidence/fabric/gold/`.

**Preparação em 12/11:** [modelo e roteiro M04](../../data-model.md), quatro scripts T-SQL, oito testes locais e [ensaio relacional real](../../../evidence/m04/local-gold.json). Reconciliação local de 8.052 coletas e 518 versões observadas; nenhuma execução Fabric. Adaptador da versão oficial depende do contrato aceito no M03; os cinco critérios permanecem abertos.

**Pacote operacional M04:** [roteiro completo](../../m04-fabric.md), notebook **07** que consome o `consumer_contract` do **06 oficial M03**, seis arquivos de upload, nove scripts Warehouse em ordem e sete cenários sintéticos com comparação integral/rollback. Entrada, publicação oficial, validação e repetição estão preparadas. [Verificação do pacote](../../../evidence/m04/execution-package.json); execução Fabric e aceite continuam pendentes.

## M05 — Orquestração e recuperação entre camadas

**Resultado:** uma execução parametrizada de ponta a ponta, com recuperação sem publicação parcial.

**Passos:** ligar Copy, notebooks e carga Gold; separar tentativa de publicação válida; configurar dependências de sucesso, erros e parâmetros; provocar falhas delimitadas; recuperar.

- [ ] Pipeline mestre executa recebimento → Bronze → Silver → Gold com parâmetros de fonte, hash/versão e escopo; um identificador permite relacionar as auditorias dos itens.
- [ ] Execução verde termina com reconciliação do lote e da versão publicada; os marcadores avançam somente após a publicação válida.
- [ ] Falha provocada em Silver impede atualização Gold; fatos e marcador da versão Gold anterior permanecem iguais.
- [ ] Falha provocada na carga Gold mantém o último estado válido para consumo e permite nova tentativa controlada, sem duplicação ou perda.
- [ ] Recuperação das duas falhas e repetição completa aprovadas; agendamento/evento delimitado exercitado uma vez e desabilitado ao fim do laboratório, com runbook de diagnóstico.

**Métrica de saída:** cinco provas operacionais: execução verde, bloqueio em Silver, proteção em Gold, recuperação e repetição completa. Não presumir transação única entre Lakehouse e Warehouse.

**Arquivos previstos:** definições reais exportadas em `fabric/` (estrutura nativa confirmada na integração), `docs/runbooks/recovery.md`, `evidence/fabric/orchestration/`.

## M06 — Laboratório Dataflow Gen2

**Resultado:** praticar Power Query/Dataflow Gen2 com responsabilidade pequena e verificável.

**Passos:** usar o mesmo snapshot IBGE, selecionar código/nome/UF, tipar e normalizar espaços; gravar tabela de laboratório separada; comparar com a referência canônica. Não fazer toda origem passar por Copy e Dataflow em sequência.

- [ ] Disponibilidade e variante do Dataflow Gen2 confirmadas no trial/tenant, incluindo suporte aplicável a Git/implantação.
- [ ] Fluxo executado em tabela de laboratório identificada, com os 92 códigos do snapshot de referência, sem virar uma segunda fonte canônica de município.
- [ ] Tipos e unicidade dos códigos aprovados; comparação com a projeção equivalente da referência apresenta zero diferenças inexplicadas.
- [ ] Nova atualização não duplica a tabela; erro de transformação provocado em fixture é diagnosticado e recuperado, com saídas registradas.
- [ ] Documentação explica quando escolher Copy, notebook ou Dataflow para esse caso e referencia a definição exportada real.

**Métrica de saída:** um fluxo válido, uma repetição e um erro recuperado. Se o recurso estiver indisponível, marcar bloqueio/condição e decidir redução explicitamente; não contar código não executado como laboratório concluído.

**Arquivos previstos:** item real em `fabric/`, `docs/dataflow-gen2.md`, `evidence/fabric/dataflow/`.

## M07 — Segurança e governança

**Resultado:** demonstrar quem pode fazer o quê, por qual caminho de acesso.

**Passos:** inventariar papéis e acessos; definir matriz de testes; validar com identidade de leitura sem privilégios administrativos; separar SQL e OneLake/Spark; executar laboratório de mascaramento e, se disponíveis, rótulos.

- [ ] Matriz explica Admin/Member/Contributor/Viewer e compartilhamento de itens; seis casos de acesso são definidos antes do teste, cobrindo leitura, escrita, itens e caminhos SQL/OneLake.
- [ ] Os seis casos são executados com identidades e papéis apropriados, com resultados esperados registrados; não usar sessão administrativa como prova de restrição de leitor.
- [ ] RLS regional testada com identidade de leitura e fixture de pelo menos duas UFs em tabela de laboratório separada: linhas permitidas visíveis, linhas restritas invisíveis; CNPJ oficial não é artificialmente classificado como segredo.
- [ ] Mascaramento de campo fictício demonstrado e distinguido de autorização/anonimização. Uma restrição SQL não é apresentada como proteção automática aos arquivos.
- [ ] Registro de governança contém responsabilidades, conexões/segredos fora do Git e condições de rótulos/auditoria administrativa; aplicar rótulo se houver permissão/licença, ou registrar a limitação como NÃO APLICÁVEL sem reivindicar execução.

**Métrica de saída:** 6/6 casos da matriz e teste RLS aprovados. Falta de identidade de leitura bloqueia esse aceite; teste administrativo simulado não substitui essa condição.

**Arquivos previstos:** `sql/labs/security.sql`, `docs/security-matrix.md`, `evidence/fabric/security/`. Usar aliases de papel nas evidências versionadas, sem dados pessoais de conta.

## M08 — Git e implantação real

**Resultado:** mudança versionada e promovida entre dois ambientes, com restauração demonstrada.

**Passos:** começar a preparar integração já em M02; definir destino remoto privado e autorizações quando essa ação for necessária; consultar suporte por tipo de item; conectar dev; implantar para um workspace de teste na capacidade disponível. Não pressupor três ambientes ou outra capacidade paga.

- [ ] Repositório remoto/destino aprovado e workspace dev conectado ao Git; uma alteração de item real é sincronizada e seu commit identificado. O Git local já existente é a base, não prova de integração do workspace.
- [ ] Duas áreas de trabalho distintas (dev e teste) têm configurações/conexões separadas; nenhum segredo ou identificador pessoal fica no código, e o suporte de cada item à implantação é registrado.
- [ ] Uma mudança dos itens suportados é promovida por deployment pipeline e executada no destino, com reconciliação da fatia e comparação dos resultados esperados.
- [ ] Uma versão anterior é restaurada e testada no destino; recuperação documentada sem depender de apagar ambientes ou dados para fingir rollback.
- [ ] Validação automática do provedor escolhido executa os checks locais pertinentes; runbook permite repetir a implantação. Se um item não tiver suporte nativo, exercitar a alternativa real e registrar a diferença; integração nativa bloqueada não é marcada como praticada.

**Métrica de saída:** uma sincronização Git, uma implantação dev → teste, uma restauração e uma execução reconciliada em teste, todos vinculados a versões.

**Arquivos previstos:** `fabric/`, `config/environments.example.json`, `docs/deployment.md`, configuração de CI do provedor efetivamente escolhido, `evidence/fabric/deployment/`.

## M09 — Operação, diagnóstico e otimização medida

**Resultado:** localizar uma falha e avaliar uma intervenção com evidência de antes/depois.

**Passos:** acompanhar runs, bytes, linhas, duração e rejeições desde M02; revisar Monitoring hub e Job management; inventariar Spark pool/capacidade; escolher um problema observado; medir intervenção pertinente.

- [ ] Visão de execução relaciona run_id, origem/versão, contagens, rejeições, duração e estado de publicação; uma execução normal e uma falha são localizáveis por esse registro.
- [ ] Incidente operacional é explicado por evidência de sessão/job/capacidade quando disponível. O HTTP 430 já registrado é ponto de partida, mas sua causa não pode ser declarada confirmada sem essa inspeção.
- [ ] Protocolo de desempenho fixa consulta/job, dados, runtime/pool e condições de cache; captura três medições de baseline e três após uma intervenção escolhida com motivo.
- [ ] Relatório informa mediana, volume/lidas/arquivos ou plano pertinente, custo/consumo quando disponível e reconciliação dos dados. Ganho nulo ou regressão são resultados válidos se medidos honestamente; manter a mudança só quando justificada.
- [ ] Runbook cobre sessão Spark, falhas, retenção, consumo e encerramento dos laboratórios. OPTIMIZE/VACUUM, particionamento e V-Order só são aplicados com justificativa e explicação de efeitos, especialmente sobre time travel.

**Métrica de saída:** um diagnóstico reproduzível, um experimento com seis medições e nenhuma divergência de negócio causada pela intervenção. Registrar duração/volume do pipeline e do consumo Gold, mesmo que o experimento priorizado esteja em outro componente.

**Arquivos previstos:** `docs/operations.md`, `docs/performance.md`, consultas/notebooks específicos do experimento, `evidence/fabric/operations/` e `evidence/fabric/performance/`.

## M10 — Streaming sintético, KQL e Activator

**Resultado:** laboratório pequeno de eventos com ingestão, consulta temporal e regra de alerta observadas.

**Passos:** definir contrato com event_id, posto sintético, produto, unidade, event_time UTC, preço e is_synthetic=true; emitir lote finito; conectar Eventstream e Eventhouse; consultar em KQL; exercitar regra Activator e encerrar o emissor.

- [ ] Gerador emite 1.000 event_ids válidos e únicos, termina automaticamente e registra a emissão. Itens/tabelas sintéticos ficam separados dos dados oficiais; endpoints/credenciais ficam protegidos.
- [ ] Eventstream → Eventhouse/KQL executado de verdade; comparar conjuntos de IDs emitidos e recebidos após estabilizar a ingestão, sem perdas inexplicadas e com duplicatas contabilizadas.
- [ ] Reinjetar 20 eventos e incluir eventos fora de ordem; consulta deduplicada conserva 1.000 IDs únicos. Documentar comportamento de event_time versus ingestion_time, sem prometer exactly-once do transporte.
- [ ] Quatro consultas KQL verificadas: preço mais recente por posto/produto, janela temporal agregada, cobertura/contagem e duplicatas/atrasos.
- [ ] Regra Activator dispara na transição controlada de um limiar e registra o resultado; canal/destinatário de eventual notificação ao próprio usuário definidos antes de habilitar envio. Guardar evidência do disparo e encerrar emissor/execuções persistentes do laboratório.

**Métrica de saída:** 1.000 IDs únicos reconciliados, reinjeções tratadas, quatro consultas corretas e pelo menos um disparo controlado observado. Se Activator ou a integração necessária estiver indisponível, registrar bloqueio e decidir o escopo explicitamente; uma simulação Python não vale como execução Activator.

**Arquivos previstos:** `scripts/generate_synthetic_events.py`, `kql/fuelwatch_lab.kql`, `config/streaming.example.json`, definições reais em `fabric/`, `evidence/fabric/streaming/`.

## M11 — Consumo e entrega final

**Resultado:** demonstração curta que outra pessoa consegue entender e reproduzir, com limites explícitos.

**Passos:** construir modelo semântico e uma página Power BI; confrontar medidas com T-SQL; revisar dicionário, operação e evidências; executar roteiro final. Publicação externa é uma decisão separada.

- [ ] Uma página Power BI responde evolução semanal, comparação municipal/regional e cobertura, sempre com produto, unidade, período e quantidade de observações explícitos.
- [ ] Pelo menos três medidas do relatório reconciliam com consultas T-SQL de referência; filtros e agregação semanal preservam o denominador correto, sem média de médias indevida.
- [ ] Três demonstrações finais documentadas: carga válida, repetição e falha seguida de recuperação; versões de código/origem, runs e resultados podem ser rastreados.
- [ ] README, dicionário de dados, desenho, configuração, recuperação e implantação permitem reproduzir a fatia em outro ambiente autorizado; segredos/contas ficam fora dos artefatos e limitações de trial são registradas.
- [ ] Revisão final confere critérios do roadmap, pendências e recursos ativos; cada experiência de currículo/portfólio se apoia em execução/evidência real. Nenhuma afirmação de resultado, economia ou desempenho é inventada.

**Métrica de saída:** três perguntas de negócio respondidas, três medidas reconciliadas, três cenários operacionais demonstrados e nenhum bloqueio obrigatório oculto.

**Arquivos previstos:** modelo/relatório reais em `fabric/` conforme suporte, `docs/demo.md`, `docs/data-dictionary.md`, atualização do README e índice final `evidence/README.md`.

## Frentes que acompanham os marcos

| Frente | Já existe | Próxima ação | Aceite final |
| --- | --- | --- | --- |
| Git | Repositório local e commits | Preparar destino remoto/integração junto de M02 | M08 |
| Segurança | Segredos fora do projeto | Registrar acessos/conexões e princípio de menor privilégio | M07 |
| Observabilidade | Runs, hashes e reconciliação Bronze | Repetir auditoria por camada e registrar runtime/capacidade | M09 |
| Qualidade | Contrato e testes locais; repetição Bronze | Executar regras equivalentes na Silver | M02–M05 |
| Custo e trial | Trial informado; HTTP 430 documentado | Registrar expiração, SKU/pool/região e sessões; execução serial | Todos |

## O que significa terminar

**Núcleo batch concluído:** M00–M05 e M07–M09 aceitos. Inclui dados corretos, modelo de consumo, correções históricas, recuperação, segurança, implantação e operação; não basta haver tabelas.

**Projeto completo no escopo combinado:** núcleo batch mais M06, M10 e M11 aceitos. Restrições administrativas/licenciamento podem tornar somente os exercícios explicitamente condicionados não aplicáveis, com justificativa e decisão registrada. Bloqueios de requisitos obrigatórios mantêm o projeto como parcial até execução ou redução de escopo acordada. Laboratório de streaming permanece parte do projeto completo.

**Fora do escopo inicial:** clima/INMET, população, predição, API/backend, frontend próprio, carga nacional de vários anos e operação permanente. Não usar essas extensões como requisito para concluir o projeto atual.

## Próximo bloco concreto: M04

1. Preservar os aceites M00–M03 e consumir o contrato oficial do run 6929bb98: silver_preco_publicado, Delta 0, snapshot 3da66482.
2. Seguir o roteiro M04 já preparado e conferir as dependências do Warehouse antes de criar/executar itens.
3. Reconciliar o export da versão selecionada, executar os cenários sintéticos e publicar o modelo dimensional somente após seus checks.
4. Validar SCD2 observado, fato de coleta, consumo semanal e repetição no Warehouse com evidências reais.
5. Registrar os resultados M04 sem estender os aceites anteriores a etapas ainda não executadas.

M03 concluído: 17 cenários sintéticos mais seleção oficial/repetição no Fabric. Sessão Spark encerrada. Próxima execução é M04, não repetir M03 sem motivo.

## Registro de acompanhamento

Em cada sessão, acrescentar uma linha. As mudanças de estado exigem links para evidência, não apenas uma descrição de esforço.

| Data local | Marco | Estado | Evidência/resultado | Próximo passo |
| --- | --- | --- | --- | --- |
| 11/11/2026 | M00 | CONCLUÍDO | Perfil real + fatia local + 10 testes | Bronze Fabric |
| 11/11/2026 | M01 | CONCLUÍDO | Dois runs Bronze + comparação Delta 0 → 1, sem diferenças | Silver PySpark |
| 12/11/2026 | Roadmap | REVISADO | Critérios e sequência definidos; execução de dados continua pausada | Retomar M02 quando solicitado |
| 12/11/2026 | M02 | EM ANDAMENTO | Retomada solicitada; notebooks e bundle preparados, 14 testes locais; aceite Fabric aberto | Upload e execução do notebook 03 |
| 12/11/2026 | M02 | EM ANDAMENTO | JSON do notebook 03 conferido: 92 municípios, zero ambiguidade e hashes aprovados | Parar sessão 03; executar notebook 04 |
| 12/11/2026 | M02 | EM ANDAMENTO — 4/5 critérios | JSON 8405ed03 conferido: fixture aprovado, Silver Delta 0, 8.052 coletas, 502 postos, 27 municípios, 26 sinais e zero diferenças de negócio | Repetir notebook 04 com os mesmos snapshots; comprovar same_business_as_previous=true |
| 12/11/2026 | M03 | PREPARAÇÃO LOCAL | 15 tentativas sintéticas reconciliadas, nove testes específicos; pacote M02 preservado | Aceitar Silver/repetição M02 e implementar notebook 05 |
| 12/11/2026 | M03 | PRONTO PARA EXECUÇÃO | Notebook 05, três arquivos de upload, 17 cenários e 28 testes locais; formato/sintaxe aprovados, sem execução Spark/Delta | Upload em m03_input; importar 05; executar Run all e enviar JSON |
| 12/11/2026 | M03 | LAB FABRIC VALIDADO | Experimento ccbdb9dc: 17 cenários e 27 checks do retorno; recuperação correta e Silver oficial inalterada | Parar sessão 05; integrar controle ao fluxo oficial |
| 12/11/2026 | M02 | CONCLUÍDO — 5/5 critérios | JSON 5f55cb03 conferido: Delta 0 → 1, same_business_as_previous=true, contagens estáveis e comparação integral sem diferenças | Parar sessão 04; próximo marco M03, notebook 05 pendente |
| 12/11/2026 | M04 | PREPARAÇÃO LOCAL | T-SQL e fixtures preparados; núcleo relacional e SCD2 verificados localmente sobre o snapshot M02 | Concluir M03; validar laboratório Warehouse e integrar snapshot aprovado |
| 12/11/2026 | M03 | CONCLUÍDO — 5/5 critérios | Run 6929bb98 executado na guia Fabric: 34 checks, 8.052 coletas, seleção Delta 0 → 0 no replay, M02 preservado e sessão encerrada | M04 — Gold/Warehouse; 4/12 marcos concluídos |

## Dependências e referências oficiais

Disponibilidade e permissões devem ser conferidas na conta ao iniciar cada laboratório; não assumir que todo item tem o mesmo suporte de Git, implantação ou trial.

- [Guia vigente da DP-700](https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/dp-700): os três grupos são implementar/gerenciar, ingerir/transformar e monitorar/otimizar. M02–M05/M06/M10 trabalham ingestão/transformação; M07/M08 e orquestração trabalham gestão; M05/M09/M10 trabalham diagnóstico/operação. O roadmap não afirma cobrir sozinho toda a prova; revisar lacunas como domínios, Airflow e recursos não exercitados separadamente, sem ampliar automaticamente o produto.
- [Requisitos da integração Git](https://learn.microsoft.com/en-us/fabric/cicd/git-integration/git-get-started): acesso ao provedor, capacidade e configurações de tenant precisam ser verificados.
- [Planejamento de CI/CD e suporte por item](https://learn.microsoft.com/en-us/fabric/fundamentals/understand-best-practices-fabric-cicd): conferir matriz de Git/deployment e conexões entre ambientes antes de escolher o mecanismo.
- [Dataflow Gen2 com CI/CD e Git](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-cicd-and-git-integration): confirmar a variante e seus pré-requisitos no laboratório.
- [Destinos Eventstream](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/add-manage-eventstream-destinations) e [Activator](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/activator-introduction): validar rota disponível e condições antes do laboratório de alertas.
- [Concorrência Spark](https://learn.microsoft.com/en-us/fabric/data-engineering/spark-job-concurrency-and-queueing): dimensionar sessões e observar Job management, preservando a preferência por trial.
