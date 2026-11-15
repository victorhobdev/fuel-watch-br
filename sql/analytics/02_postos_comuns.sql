-- Comparação de primeiros semestres, preservando produto, unidade e localização.
-- As somas e contagens permitem calcular a média de cada posto com precisão.
CREATE OR ALTER VIEW analise_hist.postos_comuns_semestre AS
WITH por_posto AS (
 SELECT YEAR(data_coleta) AS ano, cnpj, uf, municipio_ibge, produto, moeda, unidade,
        COUNT_BIG(*) AS coletas, SUM(CAST(preco_venda AS decimal(18,3))) AS soma_precos
 FROM gold_hist.business_published
 WHERE MONTH(data_coleta) BETWEEN 1 AND 6
 GROUP BY YEAR(data_coleta), cnpj, uf, municipio_ibge, produto, moeda, unidade
)
SELECT a.ano AS ano_anterior, b.ano AS ano_atual, a.cnpj, a.uf, a.municipio_ibge,
       a.produto, a.moeda, a.unidade, a.coletas AS coletas_anterior,
       b.coletas AS coletas_atual, a.soma_precos AS soma_anterior, b.soma_precos AS soma_atual
FROM por_posto a JOIN por_posto b ON b.ano = a.ano + 1 AND b.cnpj = a.cnpj
 AND b.uf = a.uf AND b.municipio_ibge = a.municipio_ibge AND b.produto = a.produto
 AND b.moeda = a.moeda AND b.unidade = a.unidade;
