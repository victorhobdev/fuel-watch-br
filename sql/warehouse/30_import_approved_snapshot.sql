-- Executar no Warehouse APÓS notebook 07. Alterar somente os três valores abaixo.
DECLARE @lakehouse sysname = 'lh_fuelwatch';
DECLARE @lakehouse_schema sysname = 'dbo';
DECLARE @batch_id varchar(80) = 'COLAR_BATCH_ID_DO_NOTEBOOK_06';
IF TRY_CONVERT(uniqueidentifier, @batch_id) IS NULL
    THROW 51200, 'Preencher batch_id do JSON m04_transfer_ready.', 1;
DECLARE @source nvarchar(520) = QUOTENAME(@lakehouse) + '.' + QUOTENAME(@lakehouse_schema) + '.';
DECLARE @sql nvarchar(max) = N'
BEGIN TRY
    BEGIN TRANSACTION;
    IF (SELECT COUNT_BIG(*) FROM {source}m04_transfer_manifest WHERE batch_id=@batch) <> 1
        THROW 51201, ''Manifesto nao visivel ou duplicado. Aguardar sync do SQL endpoint.'', 1;
    IF NOT EXISTS (SELECT 1 FROM {source}m04_transfer_manifest WHERE batch_id=@batch
        AND source_sha256=''a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c''
        AND ibge_sha256=''2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0''
        AND silver_delta_version>=0 AND source_table=''silver_preco_publicado''
        AND TRY_CONVERT(uniqueidentifier,snapshot_id) IS NOT NULL
        AND is_synthetic=0 AND scope_id=''anp-2026-1-rj-gasolina''
        AND expected_rows=8052 AND expected_stations=502 AND expected_municipalities=27 AND expected_unusual=26)
        THROW 51202, ''Manifesto fora do baseline M02 aprovado.'', 1;
    IF (SELECT COUNT_BIG(*) FROM {source}m04_transfer_coletas WHERE batch_id=@batch) <> 8052
        OR (SELECT COUNT_BIG(*) FROM {source}m04_transfer_municipios WHERE batch_id=@batch) <> 92
        OR (SELECT COUNT_BIG(*) FROM {source}m04_transfer_calendar WHERE batch_id=@batch) <> 181
        OR (SELECT COUNT_BIG(*) FROM {source}m04_transfer_expected_posto WHERE batch_id=@batch) <> 518
        OR (SELECT COUNT_BIG(*) FROM {source}m04_transfer_expected_weekly WHERE batch_id=@batch) <> 656
        THROW 51203, ''Transferencia ainda incompleta no SQL endpoint. Nao publicar.'', 1;
    DELETE FROM gold.stage_coleta;
    DELETE FROM gold.stage_manifest;
    DELETE FROM gold.dim_data;
    DELETE FROM gold.dim_municipio;
    INSERT INTO gold.stage_coleta
        SELECT cnpj, cnpj_origem, produto, data_coleta, preco_venda, moeda, unidade, uf,
            municipio_ibge, municipio_origem, revenda_observada, bandeira_observada, preco_incomum_iqr
        FROM {source}m04_transfer_coletas WHERE batch_id=@batch;
    INSERT INTO gold.stage_manifest
        SELECT batch_id, scope_id, source_sha256, ibge_sha256, silver_delta_version, is_synthetic,
            expected_rows, expected_stations, expected_municipalities, expected_unusual, source_table, snapshot_id
        FROM {source}m04_transfer_manifest WHERE batch_id=@batch;
    INSERT INTO gold.dim_data SELECT data_sk, data, inicio_semana_iso, ano_iso, semana_iso
        FROM {source}m04_transfer_calendar WHERE batch_id=@batch;
    INSERT INTO gold.dim_municipio SELECT municipio_ibge, nome, uf
        FROM {source}m04_transfer_municipios WHERE batch_id=@batch;
    IF EXISTS (SELECT * FROM gold.stage_business_bytes EXCEPT
        SELECT CAST(cnpj AS varbinary(8000)), CAST(cnpj_origem AS varbinary(8000)), CAST(produto AS varbinary(8000)),
            data_coleta, preco_venda, CAST(moeda AS varbinary(8000)), CAST(unidade AS varbinary(8000)),
            CAST(uf AS varbinary(8000)), CAST(municipio_ibge AS varbinary(8000)), CAST(municipio_origem AS varbinary(8000)),
            CAST(revenda_observada AS varbinary(8000)), CAST(bandeira_observada AS varbinary(8000)), preco_incomum_iqr
        FROM {source}m04_transfer_coletas WHERE batch_id=@batch)
        THROW 51204, ''Valores do stage divergem da transferencia.'', 1;
    IF (SELECT COUNT_BIG(*) FROM gold.stage_coleta) <> 8052 OR EXISTS (
        SELECT cnpj, produto, data_coleta, unidade FROM gold.stage_coleta
        GROUP BY cnpj, produto, data_coleta, unidade HAVING COUNT_BIG(*) <> 1)
        THROW 51205, ''Cardinalidade do stage divergiu.'', 1;
    DELETE FROM gold.expected_posto;
    DELETE FROM gold.expected_weekly;
    INSERT INTO gold.expected_posto
        SELECT posto_sk, cnpj, revenda_observada, bandeira_observada, municipio_ibge, uf, observado_desde, observado_ate
        FROM {source}m04_transfer_expected_posto WHERE batch_id=@batch;
    INSERT INTO gold.expected_weekly
        SELECT inicio_semana_iso, ano_iso, semana_iso, municipio_ibge, produto, moeda, unidade,
            coletas, postos_observados, soma_precos, preco_minimo, preco_maximo, precos_incomuns
        FROM {source}m04_transfer_expected_weekly WHERE batch_id=@batch;
    COMMIT TRANSACTION;
    SELECT ''m04_stage_ready'' AS status, * FROM gold.stage_manifest;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;';
SET @sql = REPLACE(@sql, '{source}', @source);
EXEC sp_executesql @sql, N'@batch varchar(80)', @batch=@batch_id;
