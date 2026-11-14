IF SCHEMA_ID('analise_br') IS NULL EXEC('CREATE SCHEMA analise_br');
GO
CREATE OR ALTER VIEW analise_br.posto_semana AS
WITH base AS (
 SELECT *,
  ROW_NUMBER() OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso ORDER BY data_coleta DESC) AS ordinal,
  CAST(PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY preco_venda)
   OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS decimal(14,6)) AS preco_mediano,
  COUNT_BIG(*) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS coletas,
  SUM(preco_venda) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS soma_precos,
  MIN(uf) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS uf_min,
  MAX(uf) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS uf_max,
  MIN(municipio_ibge) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS municipio_min,
  MAX(municipio_ibge) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS municipio_max,
  MIN(bandeira_observada) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS bandeira_min,
  MAX(bandeira_observada) OVER(PARTITION BY cnpj,produto,moeda,unidade,inicio_semana_iso) AS bandeira_max
 FROM gold_br.coletas
)
SELECT cnpj,produto,moeda,unidade,inicio_semana_iso,uf,municipio_ibge,municipio_ibge_nome,
 bandeira_observada,revenda_observada,preco_mediano,coletas,soma_precos,
 CAST(CASE WHEN uf_min=uf_max AND municipio_min=municipio_max AND bandeira_min=bandeira_max THEN 1 ELSE 0 END AS bit) AS comparacao_valida
FROM base WHERE ordinal=1;
GO
CREATE OR ALTER VIEW analise_br.referencia_uf_semana AS
SELECT DISTINCT uf,produto,moeda,unidade,inicio_semana_iso,
 COUNT_BIG(*) OVER(PARTITION BY uf,produto,moeda,unidade,inicio_semana_iso) AS postos_referencia,
 CAST(PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY preco_mediano)
  OVER(PARTITION BY uf,produto,moeda,unidade,inicio_semana_iso) AS decimal(14,6)) AS mediana_uf
FROM analise_br.posto_semana WHERE comparacao_valida=1;
GO
CREATE OR ALTER VIEW analise_br.posicao_posto_semana AS
SELECT p.*,r.postos_referencia,r.mediana_uf,
 CAST(CASE WHEN p.comparacao_valida=1 AND r.postos_referencia>=10 THEN 1 ELSE 0 END AS bit) AS benchmark_elegivel,
 CASE WHEN p.comparacao_valida=1 AND r.postos_referencia>=10 THEN CAST(p.preco_mediano-r.mediana_uf AS decimal(14,6)) END AS diferenca_uf,
 CASE WHEN p.comparacao_valida=1 AND r.postos_referencia>=10 AND r.mediana_uf>0
  THEN CAST((p.preco_mediano-r.mediana_uf)/r.mediana_uf*100 AS decimal(18,6)) END AS desvio_percentual,
 CASE WHEN p.comparacao_valida=0 THEN 'atributo_ambiguo'
      WHEN r.postos_referencia IS NULL OR r.postos_referencia<10 THEN 'cobertura_insuficiente'
      WHEN p.preco_mediano>r.mediana_uf THEN 'acima'
      WHEN p.preco_mediano<r.mediana_uf THEN 'abaixo' ELSE 'igual' END AS posicao
FROM analise_br.posto_semana p LEFT JOIN analise_br.referencia_uf_semana r
 ON p.uf=r.uf AND p.produto=r.produto AND p.moeda=r.moeda AND p.unidade=r.unidade AND p.inicio_semana_iso=r.inicio_semana_iso;
GO
CREATE OR ALTER VIEW analise_br.municipio_semana AS
WITH municipios AS (
 SELECT DISTINCT uf,municipio_ibge,municipio_ibge_nome,produto,moeda,unidade,inicio_semana_iso,
 COUNT_BIG(*) OVER(PARTITION BY municipio_ibge,produto,moeda,unidade,inicio_semana_iso) AS postos_municipio,
 CAST(PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY preco_mediano)
  OVER(PARTITION BY municipio_ibge,produto,moeda,unidade,inicio_semana_iso) AS decimal(14,6)) AS mediana_municipio
 FROM analise_br.posto_semana WHERE comparacao_valida=1
)
SELECT m.*,r.postos_referencia,r.mediana_uf,
 CAST(CASE WHEN m.postos_municipio>=3 AND r.postos_referencia>=10 THEN 1 ELSE 0 END AS bit) AS benchmark_elegivel,
 CASE WHEN m.postos_municipio>=3 AND r.postos_referencia>=10 THEN CAST(m.mediana_municipio-r.mediana_uf AS decimal(14,6)) END AS diferenca_uf
FROM municipios m JOIN analise_br.referencia_uf_semana r
 ON m.uf=r.uf AND m.produto=r.produto AND m.moeda=r.moeda AND m.unidade=r.unidade AND m.inicio_semana_iso=r.inicio_semana_iso;
GO
CREATE OR ALTER VIEW analise_br.persistencia_posto AS
SELECT cnpj,uf,produto,moeda,unidade,COUNT_BIG(*) AS semanas_observadas,
 SUM(CASE WHEN benchmark_elegivel=1 THEN 1 ELSE 0 END) AS semanas_com_benchmark,
 SUM(CASE WHEN posicao='acima' THEN 1 ELSE 0 END) AS semanas_acima,
 CASE WHEN SUM(CASE WHEN benchmark_elegivel=1 THEN 1 ELSE 0 END)>=4
 THEN CAST(100.0*SUM(CASE WHEN posicao='acima' THEN 1 ELSE 0 END)/SUM(CASE WHEN benchmark_elegivel=1 THEN 1 ELSE 0 END) AS decimal(18,6)) END AS persistencia_percentual
FROM analise_br.posicao_posto_semana GROUP BY cnpj,uf,produto,moeda,unidade;
GO
CREATE OR ALTER VIEW analise_br.bandeira_contexto AS
WITH bandas AS (
 SELECT DISTINCT uf,municipio_ibge,produto,moeda,unidade,inicio_semana_iso,bandeira_observada,
 COUNT_BIG(*) OVER(PARTITION BY municipio_ibge,produto,moeda,unidade,inicio_semana_iso,bandeira_observada) AS postos_bandeira,
 CAST(PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY preco_mediano)
  OVER(PARTITION BY municipio_ibge,produto,moeda,unidade,inicio_semana_iso,bandeira_observada) AS decimal(14,6)) AS mediana_bandeira
 FROM analise_br.posto_semana WHERE comparacao_valida=1
), elegiveis AS (
 SELECT *,COUNT_BIG(*) OVER(PARTITION BY municipio_ibge,produto,moeda,unidade,inicio_semana_iso) AS bandeiras_contexto
 FROM bandas WHERE postos_bandeira>=2
)
SELECT b.*,m.postos_municipio,m.mediana_municipio,
 CAST(b.mediana_bandeira-m.mediana_municipio AS decimal(14,6)) AS diferenca_contexto
FROM elegiveis b JOIN analise_br.municipio_semana m
 ON b.municipio_ibge=m.municipio_ibge AND b.produto=m.produto AND b.moeda=m.moeda AND b.unidade=m.unidade AND b.inicio_semana_iso=m.inicio_semana_iso
WHERE b.bandeiras_contexto>=2 AND m.postos_municipio>=3;
GO
CREATE OR ALTER VIEW analise_br.comparacao_bandeira AS
SELECT DISTINCT uf,produto,moeda,unidade,bandeira_observada,
 COUNT_BIG(*) OVER(PARTITION BY uf,produto,moeda,unidade,bandeira_observada) AS contextos_comparaveis,
 CAST(PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY diferenca_contexto)
 OVER(PARTITION BY uf,produto,moeda,unidade,bandeira_observada) AS decimal(14,6)) AS diferenca_mediana_contextual
FROM analise_br.bandeira_contexto;
