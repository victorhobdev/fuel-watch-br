# Fuel Watch BR — roadmap da fase 2 após a expansão nacional

Replanejado após solicitação do usuário e aceite da carga nacional em 13/11/2026. Este documento substitui a proposta anterior de oito marcos: a numeração F2 foi reorganizada e a correspondência está no final. Não altera retroativamente M00–M11 da fase 1.

## Resultado pretendido

Um observatório nacional capaz de explicar evolução, posição relativa de postos/municípios, diferenças por bandeira e associações exploratórias com população/clima, com atualização controlada, consumo reconciliado, alertas sintéticos contextualizados e reprodução demonstrável no Fabric.

A fase passa a partir dos dados nacionais tratados. Não repetir ingestão nem voltar ao RJ como escopo principal das análises. Pilotos menores são técnicas de validação, não redução silenciosa da entrega nacional.

## Ponto de partida comprovado

- ANP nacional, primeiro semestre de 2026, já preservada em Landing/Bronze: 422.418 registros.
- Silver/Gold nacionais executadas: 422.412 coletas aceitas, seis duplicatas exatas separadas, zero inválidos/conflitos nessa entrega.
- Cobertura observada: 27 UFs, seis produtos, 7.963 CNPJs e 417 municípios; referência IBGE nacional: 5.571 municípios.
- Histórico observado: 8.159 versões de posto; agregado municipal/produto/unidade: 50.965 grupos semanais.
- Lakehouse: `silver_preco_brasil`; Warehouse: `gold_br.coletas` e `gold_br.preco_semanal`.
- Exportação real: Parquet tipado e CSV gzip com dezessete colunas, contagens e somas verificadas.
- Publicação Gold repetida sem divergência; 78 testes locais e 46 checks no GitHub naquela revisão.
- O pipeline mestre e o relatório da fase 1 continuam restritos a RJ/GASOLINA. O processamento nacional foi executado pela CLI, sem agenda nacional habilitada.

[Evidência nacional](../evidence/fabric/national/acceptance.json), [guia dos dados](dados-nacionais.md).

## Regras que acompanham todos os marcos

1. Preservar coleta individual, raw e versões aprovadas. Histórico de posto significa mudança observada, não data jurídica.
2. Produto, moeda, unidade, período, população de comparação e cobertura acompanham toda medida. GNV/m3 não se mistura com combustíveis/litro; produtos distintos também não se misturam em um preço médio.
3. Rejeição, duplicata exata, conflito, preço incomum e sinal não avaliado são categorias diferentes. Ausência de observação não é preço zero.
4. Corrigir arquivos antigos integra o fluxo. Não usar apenas MAX(data) nem tratar hash diferente como autorização automática para publicar.
5. Fonte → código → teste local → execução Fabric → aceite são estados distintos. Cada marco tem evidência real e limites registrados.
6. Trial existente primeiro. Conferir disponibilidade/capacidade na execução; qualquer recurso pago exige custo apresentado e autorização. Nenhum custo novo está autorizado por este plano.
7. Segunda identidade de segurança continua dispensada pelo usuário. Não recriar essa obrigação nem apresentar teste restrito como realizado. Labels e demais recursos condicionados dependem de licença/permissão.
8. Evoluções incrementais no mesmo repositório; preservar o baseline RJ, os snapshots nacionais aprovados, outros projetos e alterações preexistentes.
9. Não criar API/frontend próprio, previsão de preços ou operação permanente como requisitos implícitos desta fase.

## Quadro de acompanhamento

| Marco | Entrega | Estado inicial | Dependências | Evidência mínima de saída |
|---|---|---|---|---|
| F2-00 | Base nacional tratada e utilizável | CONCLUÍDO | Fase 1 | Aceite nacional + exports reais |
| F2-01 | Referências regionais, postos, municípios e bandeiras | PRÓXIMO | F2-00 | Seis respostas de negócio reconciliadas |
| F2-02 | Pipeline nacional e atualização por versão | PLANEJADO | F2-00 | Cinco cenários e uma execução ponta a ponta |
| F2-03 | Dois anos completos de histórico adicional | PLANEJADO | F2-02; análises F2-01 para regressão | Quatro semestres adicionais reconciliados |
| F2-04 | População e contexto municipal | PLANEJADO | F2-01, F2-03 | Join temporal auditado + respostas exploratórias |
| F2-05 | Clima, cobertura e associação temporal | PLANEJADO | F2-03; painel F2-04 reutilizável | Associação estação–município e análise auditadas |
| F2-06 | Power BI nacional com perguntas completas | PLANEJADO | F2-01, F2-03–05 | Até três páginas e medidas reconciliadas |
| F2-07 | Alertas sintéticos com referência histórica | PLANEJADO | F2-01, F2-02; referência aprovada | Emissão finita, KQL e acionamento real |
| F2-08 | Desempenho medido no volume e consumo finais | PLANEJADO | F2-02, F2-03, F2-06–07 | Baseline/intervenção + resultado e decisão |
| F2-09 | Reconstrução, implantação e portfólio | PLANEJADO | Demais marcos | Ambiente reconstruído e demonstração final |

**Acompanhamento inicial: 1/10 marcos aceitos.** A fração mede entregas, não esforço, tempo ou domínio da DP-700. Os cinco critérios por marco facilitam a revisão; não converter caixas marcadas em porcentagem de prontidão individual.

## F2-00 — base nacional pronta

- [x] Todas as UFs/produtos presentes no arquivo aprovado processados, sem filtro RJ/GASOLINA.
- [x] Unidades e correspondência municipal verificadas; seis duplicatas separadas e categorias reconciliadas.
- [x] Silver/Gold e SCD2/semanal confrontados integralmente com referência independente.
- [x] Publicação repetida, baseline preservado e exportação real tipada verificada.
- [x] Evidências, documentação, CI e encerramento de recursos registrados.

Aceite: `evidence/fabric/national/acceptance.json`. Não implica histórico multianual, dashboard nacional ou atualização automática, que pertencem a outros marcos.

## F2-01 — inteligência de preços sobre os dados nacionais

**Perguntas:** quem está acima da referência, onde a diferença persiste, quais municípios são mais caros e como a bandeira se relaciona com o preço?

**Contrato inicial:** produzir primeiro uma mediana de preço por CNPJ/produto/moeda/unidade/semana. As referências municipal e de UF usam essas observações semanais por posto, com um peso por posto. Isso reduz o peso adicional de postos com mais coletas na mesma semana. A média por coleta continua disponível com nome próprio; não substituir uma medida pela outra.

- [ ] Definir e versionar grãos, benchmark UF/semana, valores nominais, diferenças em R$/unidade e percentuais, empate e denominadores.
- [ ] Publicar referência regional e posição dos postos/municípios, expondo cobertura. Regras iniciais: ao menos dez postos por benchmark UF/semana e três por comparação municipal; caso insuficiente recebe status, sem ranking forçado.
- [ ] Medir persistência: percentual de semanas observadas acima da referência, com pelo menos quatro semanas para classificar persistência. Ausência não entra como zero. Mostrar se o próprio posto integra a referência; investigar exclusão do próprio posto como análise de sensibilidade quando houver cobertura.
- [ ] Comparar bandeiras nos mesmos municípios/produtos/semanas, com estratos comuns e atributos observados na data; não atribuir causalidade à bandeira.
- [ ] Entregar ao menos seis respostas reais e reconciliar os resultados com cálculo independente; cobrir mediana par/ímpar, empates, baixa cobertura, múltiplas unidades, períodos distintos e mudança de bandeira.

**Seis respostas mínimas:** evolução semanal por produto/UF; maiores diferenças municipais; postos acima da mediana; persistência dos desvios; diferenças por bandeira em contextos comparáveis; impacto da cobertura/amostra nas comparações. Resultado nulo ou insuficiência de dados são respostas legítimas se demonstrados.

Artefatos previstos: `docs/analytics-contract.md`, `sql/analytics/region_benchmarks.sql`, `station_position.sql`, `brand_comparison.sql`, testes de medidas e `evidence/phase2/analytics/`. Esta é a próxima implementação; não exige novos arquivos ANP.

## F2-02 — processamento nacional recorrente e seguro

**Resultado:** transformar os comandos nacionais já executados em um fluxo Fabric parametrizado, reutilizável e recuperável.

- [ ] Parametrizar entregas/períodos e contratos aprovados; retirar as contagens e datas fixas do semestre atual da lógica genérica, mantendo-as nos manifestos de cada versão.
- [ ] Orquestrar referência/seleção → Bronze/Silver → sincronização SQL → publicação/validação Gold, com run/batch exatos, sem escolher arbitrariamente o arquivo/lote mais recente.
- [ ] Descobrir novas entregas e revisar arquivos antigos por política explícita. Hash idêntico gera auditoria e pula transformação/publicação desnecessárias; não prometer zero tráfego HTTP sem suporte verificado da origem.
- [ ] Executar cinco cenários: entrega nova, idêntica, corrigida de período antigo, interrupção antes da publicação e recuperação. Reconciliação e publicação anterior preservadas; nenhum POST incerto é repetido sem inspeção.
- [ ] Demonstrar uma execução ponta a ponta e uma agenda em janela finita, depois desabilitada. Publicar duração, bytes, etapas puladas, erros e resultado de negócio. Manter operação contínua exige decisão explícita posterior.

Artefatos: evolução de `tools/fabric/national_*`, notebooks/SQL nacionais, definição do pipeline, `config/refresh-policy.json`, testes de versionamento e `evidence/phase2/refresh/`. Sincronização eventual do SQL endpoint é parte do contrato operacional; refresh aceito não substitui leitura dos dados esperados.

## F2-03 — série histórica nacional

**Resultado:** dois anos completos adicionais, preservando o semestre de 2026 já entregue. Candidatos: 2024 e 2025; confirmar arquivos/layouts antes da consolidação.

- [ ] Inventariar quatro semestres completos candidatos, URLs, bytes, hashes, produtos/unidades e chaves; perfilar cada layout e identificar diferenças antes de aprovar os contratos.
- [ ] Medir um piloto na trial e estimar execução/armazenamento. Manter todas as UFs/produtos dos arquivos aprovados na entrega final, sem trocar a meta nacional por um recorte não declarado.
- [ ] Processar e reconciliar os quatro semestres por arquivo/UF/produto/unidade; preservar 2026H1. Registrar as contagens realmente observadas, não multiplicar as contagens atuais como estimativa de aceite.
- [ ] Unificar grão e histórico de postos entre semestres: mesma coleta nas fronteiras não duplica; correções reconstroem os intervalos e associações afetados, sem sobreposição ou dimensões independentes incoerentes por semestre.
- [ ] Executar consultas de evolução e painel de postos comuns entre períodos, distinguindo mudança de preço e mudança da amostra. Comparações são nominais; inflação exige um enriquecimento separado antes de falar em variação real.

Artefatos: catálogos de fontes/escopos, contratos de layout, histórico dimensional e `evidence/phase2/history/`. A ambição é quatro semestres históricos mais o semestre já existente, se os candidatos forem confirmados; não apagar 2026 para cumprir uma janela de dois anos.

## F2-04 — população e porte municipal

**Resultado:** responder se porte municipal se associa a preços/dispersão e como a cobertura da pesquisa se distribui.

- [ ] Selecionar fonte/tabela oficial, edição, data de referência, unidade e política de revisão após inspecionar os metadados e uma amostra real.
- [ ] Vincular código IBGE + referência temporal, explicitando vigência e alterações territoriais. Não aplicar silenciosamente uma população atual a todos os anos históricos.
- [ ] Garantir uma referência elegível por município/período: join não altera número de coletas nem soma dos preços. Ausências/ambiguidades recebem status rastreável.
- [ ] Publicar municípios associados/não associados e percentual de cobertura, sem meta artificial de 100%.
- [ ] Entregar ao menos duas respostas exploratórias com tamanho da amostra, dispersão e limites. População não é volume de combustível vendido nem justificativa automática para ponderar o preço.

Artefatos: referência populacional datada, contrato de join, `sql/analytics/population_prices.sql`, testes e `evidence/phase2/population/`.

## F2-05 — clima e associação município-semana

**Resultado:** explorar associação entre chuva/temperatura e preços com cobertura meteorológica auditável.

- [ ] Validar arquivos INMET, acesso, metadados, sentinelas, unidades, cadência e fuso; medir amostra antes da carga histórica.
- [ ] Obter geografia municipal oficial adequada e referência de estações, com fonte/vigência. Definir por escrito estação elegível, método, distância máxima e ausência de cobertura antes de interpretar os resultados; nada de coordenadas inventadas ou fuzzy matching silencioso.
- [ ] Agregar variáveis meteorológicas em tabela própria por município-semana, com horas/dias válidos e completude. Regra candidata: 80% da cadência esperada por variável, sujeita à cadência oficial validada; registrar a regra aprovada e eventuais mudanças.
- [ ] Publicar estações, distâncias, municípios/semanas associados e ausências; join com preços não multiplica a fato. Sem estação elegível, registrar ausência em vez de forçar correspondência.
- [ ] Responder ao menos duas perguntas exploratórias e confrontar sazonalidade/localização como fatores de confusão; não afirmar causalidade ou esconder associação nula.

Artefatos: referência geográfica e de estações, `config/weather.json`, transformações meteorológicas, `sql/analytics/weather_prices.sql`, testes e `evidence/phase2/weather/`. A disponibilidade das fontes e cobertura será verificada neste marco; não é uma dependência já resolvida.

## F2-06 — produto analítico no Power BI

**Resultado:** substituir o consumo principal restrito ao RJ por uma experiência nacional coerente, preservando o relatório antigo como baseline.

- [ ] Definir modelo semântico nacional e filtros de produto/unidade/UF/município/período; contagens de observações/postos e cobertura acompanham os preços.
- [ ] Entregar até três páginas: panorama temporal e cobertura; postos/municípios/bandeiras; contexto populacional/meteorológico. Atualizar progressivamente as páginas quando suas dependências ficarem prontas, sem esperar clima para mostrar os primeiros resultados nacionais.
- [ ] Reconciliar todas as medidas decisórias com SQL/cálculo independente em total, filtros, semanas e períodos; medianas e referências por posto não podem virar média de médias no DAX.
- [ ] Exercitar Direct Lake versus DirectQuery se disponível na capacidade atual, registrando suporte, fallback, comportamento de segurança, correção e limites observados. Escolher o modo final pela evidência, sem contratar recurso só para cumprir a tecnologia da primeira proposta.
- [ ] Conferir renderização real e os principais filtros/interações, unidade/escopo visíveis e tratamento de cobertura insuficiente. Não chamar um arquivo aceito pela API de relatório validado.

Artefatos: modelo/relatório nacionais, definições revisadas, medidas/documentação e `evidence/phase2/consumption/`. Segurança restrita não será declarada comprovada por esses testes administrativos.

## F2-07 — alerta sintético contextualizado

**Resultado:** usar o histórico oficial aprovado como referência para eventos sintéticos, com interpretação e controle de duplicação.

- [ ] Fixar versão do benchmark, produto/unidade/UF/período e política de stale/missing benchmark. Não vincular um evento a um baseline futuro ou uma mediana desconhecida no momento do evento sem explicação.
- [ ] Criar cenários determinísticos de preço abaixo/dentro/acima da referência, duplicatas, atraso e ausência de benchmark; IDs e payloads preservados no manifesto sintético.
- [ ] Emitir lote finito de 1.000 IDs únicos com vinte reinjeções e eventos fora de ordem; reconciliar conjuntos/payloads após ingestão e consultas KQL.
- [ ] Observar regra Activator e ação de auditoria reais, conferindo a política de ações repetidas e comportamento de eventos atrasados. Não presumir exactly-once do transporte nem de notificações.
- [ ] Parar emissor/regra/destinos e reler o estado. Nenhum envio externo é presumido autorizado; se necessário, canal/destinatário e autorização são definidos antes de habilitar.

Artefatos: contratos de evento/benchmark, consultas KQL, regra/action bindings e `evidence/phase2/streaming/`. O streaming continua sintético e separado da fonte ANP.

## F2-08 — desempenho no uso final

**Resultado:** diagnosticar um gargalo real no fluxo ampliado e avaliar uma intervenção sem alterar o negócio.

- [ ] Capturar baseline por etapa do pipeline e consultas representativas: duração, volume, arquivos/bytes, cache e configuração. Ler capacidade/CU se autorizado e disponível; caso contrário registrar não medido.
- [ ] Escolher intervenção pelo gargalo observado, sem exigir MERGE, particionamento, OPTIMIZE ou V-Order por lista. Registrar hipótese e variáveis controladas antes de medir.
- [ ] Executar pelo menos três medições por condição, com aquecimentos separados e ordem alternada quando viável. Se o alvo for apenas uma consulta, não declarar ganho fim a fim.
- [ ] Reconciliar conteúdo completo ou projeção pertinente antes/depois e registrar mediana/dispersão, resultado, riscos e decisão. Ganho nulo/regressão são resultados válidos.
- [ ] Exercitar compactação/time travel/retenção em laboratório quando pertinente; VACUUM somente em cópia descartável com efeito de retenção demonstrado. Preservar snapshots oficiais e de recuperação.

Artefatos: protocolo e notebook/query do ensaio, métricas do fluxo nacional e `evidence/phase2/performance/`. Resultados do ensaio anterior com 8.052 linhas não são evidência de ganho no novo volume.

## F2-09 — reconstrução e apresentação final

**Resultado:** demonstrar que a solução ativa e seus resultados podem ser reconstruídos/revistos, com afirmações de portfólio sustentadas.

- [ ] Inventariar dependências ativas versus itens legados/laboratórios/gerenciados; confirmar o inventário atual em vez de assumir que o número de 23 pendências Git permaneceu igual após novas criações.
- [ ] Versionar/revisar os artefatos necessários ao fluxo ativo e seus bindings de exemplo. Não exigir sincronizar todos os itens; documentar alternativa de reconstrução para tipos sem suporte.
- [ ] Reconstruir em workspace vazio autorizado na trial, executar, comparar os dados e promover/restaurar uma mudança. O teste anterior dev→test é base, não prova automática da solução ampliada.
- [ ] Executar CI pertinente e registrar commit, fontes, jobs, outputs e limitações. Automatizar promoção só quando houver ganho operacional/didático; não chamar CI de testes de CD completo.
- [ ] Entregar arquitetura, dicionário, decisões, roteiro de demonstração, perguntas respondidas e inventário de recursos final. Fazer exercício de explicação/diagnóstico independente para avaliar aprendizado, sem converter o desempenho do agente em domínio do usuário.

Artefatos: runbook de reconstrução, exports revisados, pipeline de implantação, índice de evidências e `docs/demo-phase2.md`. Segredos permanecem fora do Git; exports públicos são sanitizados antes de publicação externa.

## Ordem de execução e entregas intermediárias

1. **F2-01:** respostas novas usando os dados já prontos.
2. **F2-02:** fluxo nacional parametrizado e atualização recuperável.
3. **F2-03:** dois anos completos adicionais e regressão das análises.
4. **F2-04 → F2-05:** população e clima, com cobertura/associação validadas.
5. **F2-06:** consumo principal consolidado; uma primeira página nacional pode ser entregue logo após F2-01 e atualizada durante os demais marcos.
6. **F2-07:** alerta contextualizado; pode ser encaixado após referência histórica e fluxo nacional estáveis, sem depender do clima.
7. **F2-08 → F2-09:** medição do uso ampliado, reconstrução e apresentação.

Versionamento, qualidade, auditoria e medição básica de execução acompanham todos os marcos; não são adiados até o último bloco. Este plano não impõe execução com subagentes, worktrees ou TDD integral. Usar testes proporcionais, com fixtures duráveis nos contratos de maior risco.

Não foi fixado prazo: depende do perfil histórico, cobertura meteorológica, disponibilidade remanescente da trial e tempo de trabalho. Esses fatores serão medidos no início dos blocos, sem criar perguntas de autorização para escolhas rotineiras.

## Registro de acompanhamento

| Marco | Estado | Critérios aceitos | Evidência | Próxima ação |
|---|---|---:|---|---|
| F2-00 | CONCLUÍDO | 5/5 | Aceite nacional | Usar como base |
| F2-01 | PRÓXIMO | 0/5 | Ainda não executado | Contrato dos benchmarks e primeiras consultas |
| F2-02 | PLANEJADO | 0/5 | Ainda não executado | Parametrização e desenho do fluxo nacional |
| F2-03 | PLANEJADO | 0/5 | Ainda não executado | Inventário/perfil dos quatro semestres |
| F2-04 | PLANEJADO | 0/5 | Ainda não executado | Metadados e amostra populacional |
| F2-05 | PLANEJADO | 0/5 | Ainda não executado | Metadados INMET e geografia municipal |
| F2-06 | PLANEJADO | 0/5 | Ainda não executado | Modelo nacional e primeira página |
| F2-07 | PLANEJADO | 0/5 | Ainda não executado | Contrato de evento/benchmark |
| F2-08 | PLANEJADO | 0/5 | Ainda não executado | Selecionar consulta/etapa e registrar baseline |
| F2-09 | PLANEJADO | 0/5 | Ainda não executado | Mapear dependências ativas |

Estados de trabalho: investigação/contrato → código preparado/testes locais → execução Fabric → aceito por evidência. Marcar critério somente com resultado verificável; testes e medições futuras não são resultados desta sessão de planejamento.

## Correspondência com o rascunho anterior

| Marco antigo | Novo destino |
|---|---|
| F2-01 análises sobre RJ | F2-01, agora nacional |
| F2-02 expansão/histórico | F2-00 já entregue + F2-03 histórico |
| F2-03 população | F2-04 |
| F2-04 clima | F2-05 |
| F2-05 atualização | F2-02 |
| F2-06 performance | F2-08 |
| F2-07 consumo/alertas | F2-06 + F2-07, separados |
| F2-08 reprodução/portfólio | F2-09 |

## Estudo e currículo

O Git seletivo já praticado permanece válido para estudo e para a afirmação de integração Git. Sincronização adicional só entra quando viabilizar revisão, dependências ou recuperação. Não há meta artificial de quantidade de itens.

O projeto continua distinto da cobertura integral da DP-700. Shortcuts/mirroring, Spark Structured Streaming/checkpoints, projetos de banco, domínios e outros controles podem ser estudados em laboratórios independentes, sem virar dependências implícitas do observatório. Labels permanecem condicionados à licença/permissão. Não reabrir o requisito dispensado da segunda identidade.

## Fontes e dependências ainda a verificar na execução

- [ANP — série histórica](https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/serie-historica-de-precos-de-combustiveis): quatro arquivos/layouts históricos candidatos.
- [IBGE — estimativas populacionais](https://www.ibge.gov.br/estatisticas/sociais/populacao/9103-estimativas-de-populacao.html): edição e compatibilidade temporal/territorial.
- [INMET — dados históricos](https://portal.inmet.gov.br/dadoshistoricos): acesso, qualidade e cobertura; geografia municipal oficial complementar ainda a selecionar.
- [DP-700 — guia oficial](https://learn.microsoft.com/pt-br/credentials/certifications/resources/study-guides/dp-700): trilha de estudo, não definição de todas as features do produto.

Este replanejamento reutiliza os candidatos identificados antes; não afirma nova inspeção de cada arquivo histórico, medição de custo ou validação de cobertura climática.
