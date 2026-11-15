CREATE OR ALTER VIEW analise_hist.populacao_municipio AS
WITH base AS (
 SELECT municipio_ibge,uf,YEAR(data_coleta) AS ano_referencia,produto,moeda,unidade,populacao,
 COUNT_BIG(*) OVER(PARTITION BY municipio_ibge,uf,YEAR(data_coleta),produto,moeda,unidade) AS coletas,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY preco_venda) OVER(PARTITION BY municipio_ibge,uf,YEAR(data_coleta),produto,moeda,unidade) AS preco_mediano
 FROM analise_hist.coletas_contexto
), agregados AS (
 SELECT municipio_ibge,uf,YEAR(data_coleta) AS ano_referencia,produto,moeda,unidade,COUNT(DISTINCT cnpj) AS postos_observados
 FROM gold_hist.business_published GROUP BY municipio_ibge,uf,YEAR(data_coleta),produto,moeda,unidade
)
SELECT DISTINCT b.*,a.postos_observados,
 CASE WHEN populacao IS NULL THEN 'sem_referencia' WHEN populacao<=50000 THEN 'ate_50mil'
 WHEN populacao<=100000 THEN '50mil_a_100mil' WHEN populacao<=500000 THEN '100mil_a_500mil' ELSE 'acima_500mil' END AS porte_populacional,
 CAST(a.postos_observados AS float)*100000/NULLIF(populacao,0) AS postos_pesquisados_por_100mil
FROM base b JOIN agregados a ON b.municipio_ibge=a.municipio_ibge AND b.uf=a.uf
 AND b.ano_referencia=a.ano_referencia AND b.produto=a.produto AND b.moeda=a.moeda AND b.unidade=a.unidade;
