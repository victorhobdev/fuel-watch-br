-- Somente leitura: a atividade pode repetir esta verificacao, nunca a publicacao.
DECLARE @batch varchar(80) = '{{BATCH_ID}}';
IF TRY_CONVERT(uniqueidentifier,@batch) IS NULL THROW 51843,'Batch invalido.',1;
IF (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch AND is_synthetic=0)<>1
    THROW 51844,'Aguardar manifesto exato no SQL endpoint.',1;
IF (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_coletas WHERE run_id=@batch)
        <>(SELECT expected_rows FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch)
    OR (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_calendar WHERE run_id=@batch)
        <>(SELECT expected_calendar_days FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch)
    OR (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_municipio WHERE run_id=@batch)
        <>(SELECT expected_reference_municipalities FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch)
    OR (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_expected_posto WHERE run_id=@batch)
        <>(SELECT expected_history FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch)
    OR (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_expected_weekly WHERE run_id=@batch)
        <>(SELECT expected_weekly FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch)
    OR (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.hist_transfer_sources WHERE run_id=@batch)
        <>(SELECT expected_source_files FROM lh_fuelwatch.dbo.hist_transfer_manifest WHERE run_id=@batch)
    THROW 51845,'Aguardar tabelas completas do mesmo run no SQL endpoint.',1;
SELECT 'historical_sql_visibility_validated' AS status,@batch AS batch_id;
