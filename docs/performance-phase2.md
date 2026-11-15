# Desempenho no conjunto ampliado

Ensaio real no Warehouse, registrado em
`evidence/phase2/performance/context-query.json`.

Hipótese: materializar o resultado municipal evita recomputar as janelas e os
joins da view `analise_hist.populacao_municipio` a cada leitura. O alvo foi a
consulta completa via TDS, incluindo transferência dos resultados ao cliente.

Uma cópia foi criada em `lab_f2.population_cache`, preservando a view original.
A consulta retorna 6.914 grupos município/UF/ano/produto/unidade e percorre a
publicação histórica nacional de 2.125.547 coletas. Todos os campos e a
multiplicidade foram comparados antes de medir e em cada medição. A publicação
oficial permaneceu igual.

Após um aquecimento separado por condição, foram realizadas três medições por
condição, alternando a ordem. Mediana da view: 7,375 s; mediana da cópia: 0,105 s
(aproximadamente 70,5× mais rápida nesta consulta). Intervalos observados:
7,366–7,445 s e 0,097–0,107 s, respectivamente.

O resultado sustenta a hipótese para essa leitura. Não mede redução de tempo
do pipeline completo ou dos visuais DAX; cache do serviço não foi controlado e
CU não foi medido. A cópia continua sendo laboratório. Antes de promovê-la,
será necessário ligar sua atualização à publicação aprovada, verificar rollback
e repetir as medidas decisórias do modelo. Não apontar o modelo para uma cópia
que possa ficar desatualizada.
