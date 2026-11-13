-- Warehouse wh_fuelwatch: dados nacionais de jan-jun/2026.
-- Uma linha por coleta, sem somar ou tirar media entre produtos/unidades diferentes.
SELECT TOP (100) * FROM gold_br.coletas ORDER BY data_coleta DESC,uf,produto,cnpj;

SELECT produto,moeda,unidade,COUNT_BIG(*) AS coletas,
       COUNT(DISTINCT cnpj) AS postos,COUNT(DISTINCT uf) AS ufs,
       COUNT(DISTINCT municipio_ibge) AS municipios,
       MIN(preco_venda) AS minimo,MAX(preco_venda) AS maximo,
       SUM(preco_venda)/CAST(COUNT_BIG(*) AS decimal(18,6)) AS media_por_coleta
FROM gold_br.coletas GROUP BY produto,moeda,unidade ORDER BY produto;

SELECT uf,produto,moeda,unidade,COUNT_BIG(*) AS coletas,
       COUNT(DISTINCT cnpj) AS postos,
       SUM(preco_venda)/CAST(COUNT_BIG(*) AS decimal(18,6)) AS media_por_coleta
FROM gold_br.coletas GROUP BY uf,produto,moeda,unidade ORDER BY uf,produto;

SELECT * FROM gold_br.preco_semanal ORDER BY inicio_semana_iso,municipio_ibge,produto;

SELECT produto,unidade,classificacao_preco,COUNT_BIG(*) AS coletas
FROM gold_br.coletas GROUP BY produto,unidade,classificacao_preco ORDER BY produto,classificacao_preco;
