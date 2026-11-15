# Contexto: perguntas e limites

Resultados reconciliados no Warehouse, com referências locais independentes.
Os recibos `population-answers-fabric.json` e `weather-answers-fabric.json`, em
`evidence/phase2/context`, preservam consultas, amostras e quartis.

1. **Cidades maiores têm gasolina mais barata?** Em 2025, a mediana dos preços
   municipais foi R$ 6,09/l entre 48 municípios acima de 500 mil habitantes;
   R$ 6,19/l entre 226 municípios de 100 a 500 mil; R$ 6,26/l entre 118 municípios
   de 50 a 100 mil; e R$ 6,19/l entre 27 municípios de até 50 mil. A relação
   observada não é monotônica. São medianas municipais, com um peso por município.
2. **A cobertura da pesquisa por habitante é uniforme?** A mediana de postos
   pesquisados por 100 mil habitantes varia de 5,26 nas cidades acima de 500 mil
   a 20,20 nas de até 50 mil. Isso descreve a amostra ANP, não a quantidade total
   de postos existentes, o consumo ou vendas de combustível.
3. **Semanas mais chuvosas têm gasolina mais cara?** No RJ, primeiro trimestre
   de 2025, a mediana municipal-semanal foi R$ 6,16/l abaixo de 10 mm observados,
   R$ 6,34/l entre 10 e 40 mm e R$ 6,19/l a partir de 40 mm. As amostras foram
   153, 55 e 63 municípios-semanas. Não há ordenação simples entre chuva e preço.
4. **Chuva e temperatura podem ser interpretadas separadamente?** Nesse mesmo
   recorte, a mediana de temperatura foi 27,25 °C no grupo abaixo de 10 mm e
   25,54 °C no grupo a partir de 40 mm. Os grupos também diferem na composição
   municipal. Os 24 recortes RJ/SP por trimestre expõem essa variação, mas não
   identificam efeito independente de temperatura, chuva ou localização.

Preços são nominais. População tem referência em julho do ano e é contexto
retrospectivo. Clima usa estação elegível até 100 km da sede municipal, em UTC,
com 80% de horas válidas por variável. Chuva é soma observada sem imputação.
Semanas parciais foram excluídas das comparações meteorológicas. A seleção de
municípios e semanas com cobertura suficiente pode introduzir viés; associação
observada não demonstra causalidade.
