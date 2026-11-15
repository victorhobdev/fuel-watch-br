-- O run vem da saida do notebook, nunca de TOP(1)/MAX(data).
CREATE OR ALTER PROCEDURE gold_hist.stage_and_publish
    @batch_id varchar(80), @snapshot_sha256 varchar(64),
    @expected_previous_batch_id varchar(80), @inject_fail_before_commit bit=0
AS
BEGIN
    SET NOCOUNT ON;
    IF TRY_CONVERT(uniqueidentifier,@batch_id) IS NULL
        OR LEN(@snapshot_sha256)<>64 OR @snapshot_sha256 LIKE '%[^0-9a-f]%'
        THROW 51841,'Run ou hash de aprovacao invalido.',1;
    BEGIN TRY
        BEGIN TRANSACTION;
        IF (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_manifest
            WHERE run_id=@batch_id AND source_snapshot_sha256=@snapshot_sha256 AND is_synthetic=0)<>1
            THROW 51842,'Manifesto exato ainda nao disponivel ou nao aprovado.',1;
        DELETE FROM gold_hist.stage_coleta;
        INSERT INTO gold_hist.stage_coleta
        SELECT cnpj,cnpj_origem,produto,data_coleta,preco_venda,moeda,unidade,uf,
            municipio_ibge,municipio_origem,revenda_observada,bandeira_observada,preco_incomum_iqr
        FROM lh_fuelwatch.dbo.hist_transfer_coletas WHERE run_id=@batch_id AND is_synthetic=0;
        DELETE FROM gold_hist.stage_manifest;
        INSERT INTO gold_hist.stage_manifest
        SELECT run_id,'anp-historico-br-todos',source_snapshot_sha256,ibge_sha256,silver_delta_version,
            CAST(0 AS bit),expected_rows,expected_stations,expected_municipalities,expected_unusual,
            'hist_transfer_coletas',run_id,expected_calendar_days,expected_products,CAST(date_start AS date),CAST(date_end AS date)
        FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch_id;
        DELETE FROM gold_hist.expected_posto;
        INSERT INTO gold_hist.expected_posto
        SELECT posto_sk,cnpj,revenda_observada,bandeira_observada,municipio_ibge,uf,observado_desde,observado_ate
        FROM lh_fuelwatch.dbo.hist_expected_posto WHERE run_id=@batch_id;
        DELETE FROM gold_hist.expected_weekly;
        INSERT INTO gold_hist.expected_weekly
        SELECT inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,
            coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns
        FROM lh_fuelwatch.dbo.hist_expected_weekly WHERE run_id=@batch_id;
        DELETE FROM gold_hist.stage_source_versions;
        INSERT INTO gold_hist.stage_source_versions
        SELECT source_id,source_sha256,csv_sha256,CAST(date_start AS date),CAST(date_end AS date),accepted_rows
        FROM lh_fuelwatch.dbo.hist_transfer_sources WHERE run_id=@batch_id AND is_synthetic=0;
        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
    EXEC gold_hist.publish_gold @batch_id=@batch_id,
        @expected_previous_batch_id=@expected_previous_batch_id,
        @inject_fail_before_commit=@inject_fail_before_commit;
END;
