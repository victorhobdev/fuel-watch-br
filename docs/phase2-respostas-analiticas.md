# Respostas analíticas — ANP 2026H1

Consultas reais no Warehouse: `evidence/phase2/analytics/answers/queries.json`.
As sete visões analíticas foram comparadas integralmente com uma referência local
independente; evidência em `evidence/phase2/analytics/warehouse-verification.json`.
Contrato em `analytics-contract.md`. Cada posto tem um peso por produto/semana;
as coletas originais continuam preservadas. Estes são exemplos interpretados de
consultas nacionais, não um novo recorte do processamento.

1. **Como evoluiu a gasolina no RJ?** A mediana dos postos foi R$ 6,590/litro
   na semana iniciada em 29/12/2025 e R$ 6,610 na iniciada em 29/06/2026.
   A primeira inclui somente as coletas de janeiro pertencentes àquela semana
   ISO, com 13 postos; a última tem 230 postos e termina no limite do arquivo.
   A diferença de R$ 0,020 não representa uma cesta fixa de postos nem duas
   semanas completas. Fonte: `evolucao_uf_produto.json`.
2. **Quais municípios estavam mais acima da referência estadual?** Na última
   semana observada, Bagé/RS teve mediana R$ 7,290/litro entre nove postos,
   R$ 0,900 acima da mediana estadual de R$ 6,390 entre 238 postos. Codó/MA
   teve R$ 7,860 entre sete postos, R$ 0,870 acima da referência de R$ 6,990
   entre 65 postos. São diferenças estaduais, não um ranking de preço absoluto
   ou uma estimativa de todos os postos do município. Fonte: `municipios_acima.json`.
3. **Há postos muito acima da referência?** Uma observação de gasolina em
   Guarujá/SP atingiu R$ 9,790/litro na semana de 29/06/2026, frente a R$ 6,490
   da referência estadual: diferença R$ 3,300, ou 50,847458%. O valor incomum
   continua disponível e exige investigação; não comprova erro, abuso ou
   irregularidade. Fonte: `postos_acima.json`, com identificação rastreável.
4. **A diferença persiste?** Há postos observados acima da mediana em todas
   as 27 semanas elegíveis, incluindo os dois primeiros registros do resultado
   de persistência. O denominador são semanas efetivamente comparáveis; ausência
   de pesquisa não conta como preço abaixo. Não significa preço diário alto
   durante todo o semestre. Fonte: `persistencia.json`.
5. **Bandeiras diferem após comparar contextos semelhantes?** No AC, gasolina
   da bandeira EQUADOR teve diferença contextual mediana de R$ 0,030/litro,
   com 18 contextos comparáveis; VIBRA teve R$ 0,000 também com 18 contextos.
   Cada contexto é município/produto/unidade/semana com cobertura mínima por
   bandeira. Isto é associação descritiva, sem controlar todas as características
   dos postos e sem demonstrar efeito causal da marca. Fonte: `bandeiras_contextuais.json`.
6. **Onde a comparação tem menor cobertura?** Gasolina teve 107 postos-semanas
   sem cobertura suficiente entre 110.922 postos-semanas (110.923 coletas).
   GNV teve 1.216 entre 8.437 postos-semanas, cerca de 14,41%, contra cerca de
   0,10% na gasolina. Portanto, comparar percentuais sem informar elegibilidade
   esconderia uma diferença material da pesquisa. GNV usa R$/m³; gasolina usa
   R$/litro. Fonte: `cobertura_comparacoes.json`.

Os valores se referem ao arquivo oficial preservado de 2026H1, não a preços
atuais. Nas pontas do semestre há semanas parciais. Os arquivos JSON guardam
os demais resultados nacionais e as consultas para reprodução.
