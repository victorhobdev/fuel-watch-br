-- Núcleo relacional compartilhado: executado localmente em DuckDB; T-SQL ainda pendente.
-- Em Fabric, selecionar cada CREATE VIEW como uma consulta separada.
CREATE VIEW lab_m04.candidate_posto AS
WITH observacoes AS (
    SELECT DISTINCT cnpj, data_coleta, revenda_observada, bandeira_observada, municipio_ibge, uf
    FROM lab_m04.stage_coleta
), anteriores AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY cnpj ORDER BY data_coleta) AS ordinal,
        LAG(revenda_observada) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS nome_anterior,
        LAG(bandeira_observada) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS bandeira_anterior,
        LAG(municipio_ibge) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS municipio_anterior,
        LAG(uf) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS uf_anterior,
        LAG(DATALENGTH(revenda_observada)) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS nome_bytes_anterior,
        LAG(DATALENGTH(bandeira_observada)) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS bandeira_bytes_anterior
    FROM observacoes
), mudancas AS (
    SELECT cnpj, data_coleta, revenda_observada, bandeira_observada, municipio_ibge, uf
    FROM anteriores
    WHERE ordinal = 1 OR revenda_observada <> nome_anterior OR bandeira_observada <> bandeira_anterior
        OR municipio_ibge <> municipio_anterior OR uf <> uf_anterior
        OR DATALENGTH(revenda_observada) <> nome_bytes_anterior
        OR DATALENGTH(bandeira_observada) <> bandeira_bytes_anterior
)
SELECT CONCAT(cnpj, ':', CAST(data_coleta AS varchar(10))) AS posto_sk,
    cnpj, revenda_observada, bandeira_observada, municipio_ibge, uf, data_coleta AS observado_desde,
    LEAD(data_coleta) OVER (PARTITION BY cnpj ORDER BY data_coleta) AS observado_ate
FROM mudancas;

CREATE VIEW lab_m04.candidate_fato AS
SELECT p.posto_sk, d.data_sk, 1 AS produto_sk, s.municipio_ibge, s.cnpj_origem, s.municipio_origem,
    s.preco_venda, s.preco_incomum_iqr
FROM lab_m04.stage_coleta s
JOIN lab_m04.candidate_posto p ON s.cnpj = p.cnpj AND s.data_coleta >= p.observado_desde
    AND (s.data_coleta < p.observado_ate OR p.observado_ate IS NULL)
JOIN lab_m04.dim_data d ON s.data_coleta = d.data;

CREATE VIEW lab_m04.business_published AS
SELECT p.cnpj, f.cnpj_origem, r.produto, d.data AS data_coleta, f.preco_venda,
    r.moeda, r.unidade, p.uf, f.municipio_ibge, f.municipio_origem,
    p.revenda_observada, p.bandeira_observada, f.preco_incomum_iqr
FROM lab_m04.fato_preco_coletado f
JOIN lab_m04.dim_posto p ON f.posto_sk = p.posto_sk
JOIN lab_m04.dim_data d ON f.data_sk = d.data_sk
JOIN lab_m04.dim_produto r ON f.produto_sk = r.produto_sk;

-- Comparação byte a byte dos textos: igualdade varchar pode ignorar espaços finais em T-SQL.
CREATE VIEW lab_m04.stage_business_bytes AS
SELECT CAST(cnpj AS varbinary(8000)) AS cnpj, CAST(cnpj_origem AS varbinary(8000)) AS cnpj_origem,
    CAST(produto AS varbinary(8000)) AS produto, data_coleta, preco_venda,
    CAST(moeda AS varbinary(8000)) AS moeda, CAST(unidade AS varbinary(8000)) AS unidade,
    CAST(uf AS varbinary(8000)) AS uf, CAST(municipio_ibge AS varbinary(8000)) AS municipio_ibge,
    CAST(municipio_origem AS varbinary(8000)) AS municipio_origem,
    CAST(revenda_observada AS varbinary(8000)) AS revenda_observada,
    CAST(bandeira_observada AS varbinary(8000)) AS bandeira_observada, preco_incomum_iqr
FROM lab_m04.stage_coleta;

CREATE VIEW lab_m04.published_business_bytes AS
SELECT CAST(cnpj AS varbinary(8000)) AS cnpj, CAST(cnpj_origem AS varbinary(8000)) AS cnpj_origem,
    CAST(produto AS varbinary(8000)) AS produto, data_coleta, preco_venda,
    CAST(moeda AS varbinary(8000)) AS moeda, CAST(unidade AS varbinary(8000)) AS unidade,
    CAST(uf AS varbinary(8000)) AS uf, CAST(municipio_ibge AS varbinary(8000)) AS municipio_ibge,
    CAST(municipio_origem AS varbinary(8000)) AS municipio_origem,
    CAST(revenda_observada AS varbinary(8000)) AS revenda_observada,
    CAST(bandeira_observada AS varbinary(8000)) AS bandeira_observada, preco_incomum_iqr
FROM lab_m04.business_published;

CREATE VIEW lab_m04.preco_semanal AS
SELECT d.inicio_semana_iso, d.ano_iso, d.semana_iso, f.municipio_ibge,
    r.produto, r.moeda, r.unidade,
    COUNT_BIG(*) AS coletas, COUNT(DISTINCT p.cnpj) AS postos_observados,
    SUM(f.preco_venda) AS soma_precos, AVG(f.preco_venda) AS preco_medio,
    MIN(f.preco_venda) AS preco_minimo, MAX(f.preco_venda) AS preco_maximo,
    SUM(CAST(f.preco_incomum_iqr AS int)) AS precos_incomuns
FROM lab_m04.fato_preco_coletado f
JOIN lab_m04.dim_data d ON f.data_sk = d.data_sk
JOIN lab_m04.dim_posto p ON f.posto_sk = p.posto_sk
JOIN lab_m04.dim_produto r ON f.produto_sk = r.produto_sk
GROUP BY d.inicio_semana_iso, d.ano_iso, d.semana_iso, f.municipio_ibge, r.produto, r.moeda, r.unidade;
