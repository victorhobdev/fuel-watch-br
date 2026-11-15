# Contexto populacional e meteorológico — validado no Fabric

As referências foram publicadas e validadas no Fabric pelo notebook
`15_context_references`, job `68240dd3-19a0-40fc-9f49-96db4c66cb6d`.
Os joins em `analise_hist.coletas_contexto` mantêm as 2.125.547 coletas e a soma
de preços, com unicidade das referências conferida. As respostas exploratórias,
medidas DAX por porte e a página de contexto do relatório histórico foram
reconciliadas e renderizadas. A cobertura climática permanece descritiva e
explicita ausências e elegibilidade.
Evidências: `evidence/phase2/context/fabric-reference-68240dd3-19a0-40fc-9f49-96db4c66cb6d.json`,
`evidence/phase2/context/warehouse-join.json` e
`evidence/phase2/deployment/rebuild-history-report-qa4.json`.

## População

Fonte oficial: API de Agregados do IBGE, tabela 6579, variável 9324, unidade
pessoas. São 16.713 referências município/ano para 2024–2026. Em 2024 há uma
ausência explícita (`...`) para o código 5101837; ela continua nula.

O join é por código municipal e ano da coleta. Trata-se de contexto retrospectivo
com referência em 1º de julho do respectivo ano, usando o snapshot consultado
agora. Não representa informação disponível na data de cada coleta nem um
backtest sem informação futura. Revisões posteriores exigem novo snapshot.

A referência local comprovou que o join mantém 2.125.547 linhas, todos os campos
originais e a soma dos preços. Todos os municípios/anos efetivamente pesquisados
têm população neste snapshot; isso não preenche artificialmente a ausência
existente na fonte nacional. População não é volume vendido nem peso para preço.
Postos pesquisados por 100 mil habitantes descrevem cobertura da pesquisa, não
o número total de estabelecimentos existentes.

## Geografia

Fonte: GeoPackage oficial `Localidades_Brasil_gpkg.zip`, produto Localidades do
Brasil 2022, snapshot publicado no portal do IBGE e consultado nesta execução.
Usam-se as colunas oficiais de latitude/longitude, em SIRGAS 2000 (EPSG:4674).

Seleção: Cidade/Sede Municipal, Cidade/Capital Federal e Distrito Estadual de
Fernando de Noronha. As 26 capitais com uma segunda representação de Capital
Estadual não geram duplicação. O resultado é uma referência única para os 5.571
códigos municipais. Não são coordenadas de postos nem centroides inventados.

## Meteorologia

Os três ZIPs anuais oficiais do INMET foram preservados: 2024 (565 CSVs), 2025
(594) e 2026 (634; pacote publicado até outubro). As amostras usam CSV separado
por `;`, codificação Latin-1, metadados antes do cabeçalho, hora UTC, temperatura
do ar em °C e precipitação horária em mm. A amostra de 2024 tem 8.784 registros,
2025 tem 8.760 e 2026 tem 7.296: cadência horária, incluindo ano bissexto.
Isso ainda não prova qualidade/completude de todos os valores.

Política definida antes de interpretar associações de preços, em
`config/weather.json`:

- Estação com coordenadas oficiais válidas no arquivo anual; IDs cuja posição
  mudou mais de 1 km entre os snapshots anuais ficam fora da seleção. Dez IDs
  foram excluídos por essa regra, evitando juntar medições de locais diferentes
  como se fossem uma estação estável.
- Selecionar a estação elegível mais próxima da sede municipal por Haversine,
  limite de 100 km, desempate por código. O ano de referência é o ano ISO da
  semana, garantindo uma associação única por município/semana nas fronteiras
  anuais. A UF da estação pode diferir da UF do município.
- Nenhum preço participa da escolha da estação. Não há troca automática para
  outra estação quando faltam medições na estação selecionada.
- Calendário meteorológico UTC, semana ISO iniciada na segunda. A ANP fornece
  data, não hora da coleta; não se infere uma correspondência horária exata.
- Completude mínima de 80% das horas esperadas, separada para temperatura e
  precipitação. As horas esperadas usam calendário, não apenas linhas recebidas.
  Semanas nas pontas do intervalo autorizado ficam explicitamente parciais.
- Vazio e sentinela -9999 são ausências; chuva zero é medição válida. Duplicatas,
  conflitos de hora, formatos e demais valores inválidos precisam ser auditados
  no processamento, antes de qualquer análise.
- O screening de temperatura usa a faixa ampla de -60 a 60 °C, como regra do
  projeto, sem atribuí-la ao controle oficial do INMET. Valores excluídos continuam
  rastreáveis no arquivo original. Precipitação negativa é inválida.
- Chuva semanal é soma **observada nas horas válidas**, sem preencher as horas
  ausentes. Mesmo com cobertura mínima de 80%, não equivale ao total completo
  da semana; a fração válida acompanha o valor.

O catálogo contém 1.793 registros estação/ano. A associação geográfica ficou
dentro do limite para 454 de 460 municípios no ano ISO 2024, 414 de 419 em 2025
e 415 de 417 em 2026. Esses números medem proximidade geográfica elegível,
**não cobertura de medições válidas**. A completude foi apurada separadamente:
1.509.541 coletas têm as duas variáveis elegíveis; 158.333 têm uma variável;
417.449 têm cobertura insuficiente para ambas; 22.796 não têm estação elegível
e 17.428 não têm medições. Esses totais foram reconciliados no Warehouse.

As relações com preços serão exploratórias, com tamanho da amostra e ausências
visíveis. Localização, sazonalidade, composição da amostra e distância da estação
são limitações; associação não demonstra causalidade.
