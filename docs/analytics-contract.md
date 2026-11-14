# Contrato analítico nacional — fase 2

Fonte inicial: `gold_br.coletas`, publicação `7e2b22fc-6fb4-4237-8481-bbc79c753103`. A referência de verificação usa o export Parquet real cujo hash está no recibo nacional. Nenhuma observação é removida da Gold para calcular comparações.

- Grão primário de comparação: CNPJ/produto/moeda/unidade/semana ISO. Primeiro calcular mediana das coletas desse posto nessa semana; depois calcular referência da UF sobre esses valores, um peso por posto.
- Atributos usados na apresentação: última coleta da semana por data. Se UF, município ou bandeira mudarem dentro da semana, a observação continua na saída com `comparacao_valida=0`, mas não entra no benchmark. A regra evita escolher arbitrariamente uma localidade/bandeira para comparação.
- Referência regional: UF/produto/moeda/unidade/semana. Mediana e quantidade de postos são expostas; mínimo de dez postos para classificar posição, calcular diferença e percentual.
- Referência municipal: mesmos produto/unidade/período, mediana dos preços semanais de posto; mínimo de três postos e benchmark UF elegível para diferença regional.
- Posição é `acima`, `igual`, `abaixo`, `cobertura_insuficiente` ou `atributo_ambiguo`. Estar acima da mediana não significa dado inválido ou fraude. Valor zero/ausência de referência não gera divisão.
- Persistência: semanas acima divididas pelas semanas com benchmark elegível, com mínimo de quatro semanas elegíveis. Exibir semanas observadas e elegíveis separadamente; ausência não é semana abaixo da referência.
- Bandeiras: comparar medianas dentro de município/produto/unidade/semana, com ao menos dois postos por bandeira e duas bandeiras elegíveis no contexto. Diferença contextual usa a mediana municipal. Na síntese por bandeira/UF, cada contexto tem um peso. Isso é comparação descritiva e não efeito causal da marca.
- Referência inclui o próprio posto. Não apresentar como comparação leave-one-out. A análise de sensibilidade poderá ser acrescentada explicitamente; não equivale a requisito já executado.
- Preços nominais em BRL/litro ou BRL/m3, sem misturar produtos. Valores analíticos e diferenças usam seis casas decimais; percentual também usa seis. Arredondamento de exibição não altera as comparações.
- Verificação: referências independentes Pandas/Decimal versus T-SQL real, preservando colunas, conteúdo e multiplicidade por fingerprints de linhas tipadas. Contagem ou soma isoladas não bastam.

Implementação: `sql/analytics/01_national_benchmarks.sql`. Referências locais: `scripts/prepare_analytics.py`. Verificação remota: `tools/fabric/phase2_analytics.py --verify`. O relatório nacional e as respostas interpretativas ainda precisam de execução/verificação próprias para fechar F2-01.
