# Fuel Watch BR — ideia inicial versus entrega

Análise de 13/11/2026. Base: proposta original anterior ao handoff, handoff de 11/11, solicitação inicial de desenvolvimento, código e evidências versionadas. Não foram reexecutadas cargas nem modificados recursos para esta análise. O documento DP-700 de 12/11 é histórico e não retrata o encerramento.

## Parecer

O núcleo didático de engenharia de dados foi construído e executado no Fabric, em aderência à arquitetura do handoff revisado. A entrega é um demonstrador de ponta a ponta com dados reais e laboratório sintético separado. Não é uma reprodução literal da primeira proposta, um observatório nacional atualizado continuamente ou uma comprovação de domínio integral da DP-700.

Os 12/12 marcos significam aceite do roadmap no escopo vigente, incluindo a dispensa expressa dos testes com segunda identidade. Não significam 100% da proposta original, da segurança testada ou do conteúdo do exame.

## Comparação

| Ideia / requisito | Entrega e avaliação |
|---|---|
| ANP + IBGE, inspeção antes de consolidar contrato | Entregue: ZIP nacional preservado, perfil de 422.418 registros/16 colunas, contrato e referência IBGE |
| Pipeline/Copy → Lakehouse → PySpark → Warehouse T-SQL | Entregue e executado; Gold reconciliada com Silver |
| Começar pequeno após validar a origem | GASOLINA/RJ, jan–jun/2026: 8.052 coletas, 502 postos e 27 municípios; IBGE de referência tem 92 municípios |
| Proposta original: dois anos e múltiplos recortes | Reduzida no handoff e no pedido inicial para primeira fatia; não demonstramos expansão nacional/multianual |
| Fato semanal na primeira proposta | Melhorada no handoff: fato de coleta preservada; 656 grupos semanais derivados |
| SCD2 | Entregue: 518 versões observadas, intervalos/associações reconciliados; não representa a data jurídica da mudança |
| Dimensão separada de bandeira | Bandeira como atributo histórico do posto; escolha prevista no handoff, sem duplicar fontes de histórico |
| Correções antigas, backfill e replay | Entregues controles por versão/hash, fixtures de correção e preservação da publicação; não houve republicação real da ANP observada no experimento |
| Watermark e MERGE na proposta original | Substituídos por snapshot aprovado e reconstrução transacional do escopo; idempotência de negócio não implica zero leitura/compute na repetição |
| Quarentena e preços incomuns | Separados; 26 preços incomuns válidos mantidos. Casos inválidos/conflitantes exercitados com fixtures identificados |
| Falhas e recuperação | Execuções reais: falhas Silver/Gold, rollback, recuperação, replay e agendamento; atraso de manifesto SQL também diagnosticado e recuperado no mesmo lote |
| Dataflow Gen2 | Laboratório real delimitado: 92 municípios, replay, erro de contrato e recuperação; repetido no ambiente de teste |
| Git e implantação | Repositório privado, CI real, deployment dev→test, execução e restauração. Git nativo seletivo do notebook 08; 23 outros itens não incluídos nesse envio |
| Dois usuários com RLS/máscara | Não executado. Usuário substituiu esse aceite por revisão de fonte e catálogo real. Policy/máscara conferidas; comportamento restrito não demonstrado |
| CLS e segurança de arquivos | Não demonstradas como laboratório independente; matriz distingue caminhos. RLS Warehouse não é proteção automática do OneLake |
| Rótulos de confidencialidade | Não aplicados; dependências de licença/permissão registradas. A função administrativa obtida depois para Git não comprova todos os requisitos de licenciamento |
| Otimização medida | Seis medições dev e seis test, com dados iguais; intervenção de shuffle em cache. Não houve experimento de compactação/VACUUM/V-Order, tuning amplo do Warehouse ou medição de CU |
| Eventstream → Eventhouse/KQL → Activator | Executado: 1.000 IDs/payloads, vinte duplicatas, dez fora de ordem, quatro consultas e uma ativação com ação de auditoria SQL; encerrado |
| Power BI enxuto | Uma página DirectQuery, cinco medidas reconciliadas e renderização real conferida. Direct Lake/2–3 páginas da primeira proposta não foram implementados |
| Evolução semanal e comparação municipal | Respondidas no recorte aprovado, com cobertura e unidade explícitas |
| Postos/municípios acima da mediana regional | Não há entrega analítica dedicada demonstrada. Média, IQR e limiar sintético não substituem essa pergunta |
| Comparação por bandeira | Atributo disponível no histórico; não foi entregue um visual/medida dedicado a essa comparação |
| Relação com clima/população | Adiada expressamente antes do desenvolvimento; não é pendência do núcleo vigente |
| Custos | Trial existente, sem capacidade paga criada; vencimento exato e consumo de CU não verificados. Agendas/emissores não ficaram em operação contínua |

## Pontos fortes

A entrega mais sólida é a cadeia de correção e rastreabilidade: bytes de origem, hashes, granularidade da coleta, snapshots selecionados, validação integral de campos, contexto de versões observadas, publicação protegida e evidências de falhas reais. São resultados mais defensáveis que contagens ou capturas isoladas.

As particularidades do Fabric foram efetivamente encontradas: capacidade/admissão Spark, compartilhamento de sessão e bibliotecas, SQL analytics endpoint versus Warehouse, atraso de visibilidade do manifesto, bindings não remapeados automaticamente, Dataflow Gen2 com definição/Execute API, Git com configurações de locatário e autenticação própria, MCP do Activator e exportação Power BI. Não foi apenas transportar um notebook Spark para outra plataforma.

## Limites de prontidão

O relatório e a Gold respondem perguntas na amostra, não monitoram o mercado nacional atual. A descoberta automática contínua de arquivos, expansão sem revisão de contrato, execução concorrente de publicadores, política de retenção/descarte, CI/CD com promoção automática e teste de recriação completa a partir de checkout limpo não foram comprovados. Existem scripts/runbooks de reconstrução e promoção, mas isso não equivale a bootstrap integral autossuficiente testado.

O Git nativo seletivo cumpre o exercício acordado; não torna o workspace inteiro versionado. O CI demonstrado executa checks; a implantação real foi validada separadamente por API. Os exports privados nativos contêm bindings de ambiente e precisam de revisão antes de publicação externa.

A documentação ainda contém cabeçalhos históricos que podem confundir estado atual, por exemplo a abertura de docs/performance.md fala em revalidação futura apesar do resultado de test ao final, e scripts-base SQL têm comentários de preparação. Os recibos e o status final são mais recentes, mas convém harmonizar a apresentação antes de compartilhar o portfólio.

## Preparação DP-700

O guia oficial vigente divide a prova entre implementar/gerenciar, ingerir/transformar e monitorar/otimizar (30–35% cada). Este projeto oferece prática nos três grupos. Não é justificável converter 12/12 marcos em percentual de cobertura da prova ou prontidão individual.

Lacunas de prática a estudar separadamente: shortcuts e mirroring, Spark Structured Streaming/checkpoints, projetos de banco de dados, domínios e controles granulares de segurança/rotulagem. O uso de DirectQuery também não substitui estudo dos modos Direct Lake. Não é necessário acrescentar todos ao produto Fuel Watch para estudá-los.

Fonte: https://learn.microsoft.com/pt-br/credentials/certifications/resources/study-guides/dp-700 (consultada em 13/11/2026).

A maior incerteza de aprendizado é autonomia: houve implementação e diagnóstico intensivos pelo agente. Execução bem-sucedida não demonstra que o usuário consegue explicar, modificar ou recuperar o fluxo sozinho. Um exercício curto de explicação e troubleshooting independente oferece uma avaliação melhor que adicionar mais dados.

## Próximas ações proporcionais, sem reabrir o projeto automaticamente

1. Consolidar a demonstração: README coerente, desenho único, resultado Power BI, três cenários e links para evidências; corrigir cabeçalhos históricos e explicitar o recorte no título do produto.
2. Se quiser fortalecer o observatório, entregar comparação por mediana regional e por bandeira, com produto/unidade/período/denominador fixos. É uma extensão analítica delimitada, não novo backend ou carga nacional.
3. Como melhoria de ciclo de vida, revisar os demais itens antes de ampliar o Git nativo e exercitar reconstrução em ambiente vazio com bindings documentados. Não confundir isso com requisito retroativo do aceite seletivo.
4. Para a prova, revisar as lacunas em laboratórios isolados e validar autonomia sobre o projeto existente. Segurança com segunda identidade permanece dispensada no projeto por decisão do usuário, não reintroduzida como obrigação.

## Evidências principais

- evidence/project-status-2026-11-13.json
- evidence/fabric/gold/README.md
- evidence/fabric/versioning/official/README.md
- evidence/fabric/orchestration/m05-acceptance-2026-11-13.json
- evidence/fabric/dataflow/m06-acceptance-2026-11-13.json
- evidence/fabric/security/implementation-review-2026-11-13.json
- evidence/fabric/deployment/native-git-verification.json
- evidence/fabric/deployment/checkpoint.json
- evidence/fabric/operations/m09-acceptance-2026-11-13.json
- evidence/fabric/streaming/daf2320c-b0bc-4eef-b908-a2dd80939088/verification.json
- evidence/fabric/consumption/measure-verification-2026-11-13.json
- evidence/fabric/operations/resource-audit-2026-11-13.json
