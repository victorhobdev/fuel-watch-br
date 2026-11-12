-- Salvar cada result set com batch_id/run e versão de código. Todos os erros devem ser zero.
SELECT 'missing_business_rows' AS check_name, COUNT_BIG(*) AS errors
FROM (SELECT * FROM lab_m04.stage_business_bytes EXCEPT SELECT * FROM lab_m04.published_business_bytes) a
UNION ALL
SELECT 'extra_business_rows', COUNT_BIG(*)
FROM (SELECT * FROM lab_m04.published_business_bytes EXCEPT SELECT * FROM lab_m04.stage_business_bytes) b
UNION ALL
SELECT 'duplicate_business_keys', COUNT_BIG(*) FROM (
    SELECT cnpj, produto, data_coleta, unidade FROM lab_m04.business_published
    GROUP BY cnpj, produto, data_coleta, unidade HAVING COUNT_BIG(*) <> 1) c
UNION ALL
SELECT 'invalid_fact_references', COUNT_BIG(*) FROM lab_m04.fato_preco_coletado f
LEFT JOIN lab_m04.dim_posto p ON f.posto_sk = p.posto_sk
LEFT JOIN lab_m04.dim_data d ON f.data_sk = d.data_sk
LEFT JOIN lab_m04.dim_produto r ON f.produto_sk = r.produto_sk
LEFT JOIN lab_m04.dim_municipio m ON f.municipio_ibge = m.municipio_ibge
WHERE p.posto_sk IS NULL OR d.data_sk IS NULL OR r.produto_sk IS NULL OR m.municipio_ibge IS NULL
UNION ALL
SELECT 'overlapping_station_intervals', COUNT_BIG(*) FROM lab_m04.dim_posto a JOIN lab_m04.dim_posto b
ON a.cnpj = b.cnpj AND a.observado_desde < b.observado_desde
AND (a.observado_ate IS NULL OR a.observado_ate > b.observado_desde)
UNION ALL
SELECT 'invalid_temporal_assignments', COUNT_BIG(*) FROM lab_m04.fato_preco_coletado f
JOIN lab_m04.dim_posto p ON f.posto_sk = p.posto_sk JOIN lab_m04.dim_data d ON f.data_sk = d.data_sk
WHERE d.data < p.observado_desde OR (p.observado_ate IS NOT NULL AND d.data >= p.observado_ate);

SELECT COUNT_BIG(*) AS coletas, COUNT(DISTINCT cnpj) AS postos,
    COUNT(DISTINCT municipio_ibge) AS municipios, SUM(CAST(preco_incomum_iqr AS bigint)) AS precos_incomuns
FROM lab_m04.business_published;

-- Contagens e soma são aditivas; postos distintos NÃO são somáveis entre grupos.
SELECT (SELECT COUNT_BIG(*) FROM lab_m04.fato_preco_coletado) AS coletas_fato,
    (SELECT SUM(coletas) FROM lab_m04.preco_semanal) AS coletas_semanal,
    (SELECT SUM(preco_venda) FROM lab_m04.fato_preco_coletado) AS soma_fato,
    (SELECT SUM(soma_precos) FROM lab_m04.preco_semanal) AS soma_semanal;

SELECT * FROM lab_m04.publication;

-- Calendário carregado deve concordar com o cálculo ISO do Warehouse.
SELECT 'invalid_iso_calendar' AS check_name, COUNT_BIG(*) AS errors
FROM lab_m04.dim_data
WHERE semana_iso <> DATEPART(ISO_WEEK, data)
    OR data_sk <> YEAR(data) * 10000 + MONTH(data) * 100 + DAY(data)
    OR ano_iso <> YEAR(DATEADD(day, 3, inicio_semana_iso))
    OR DATEDIFF(day, CAST('1900-01-01' AS date), inicio_semana_iso) % 7 <> 0
    OR data < inicio_semana_iso OR data >= DATEADD(day, 7, inicio_semana_iso);
