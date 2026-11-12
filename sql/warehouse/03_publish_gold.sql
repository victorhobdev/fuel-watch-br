-- PREPARADO, não executado no Fabric. Executar como um batch único no Warehouse.
-- Stage deve estar congelada e completa durante validação/carga, com um único escritor.
CREATE OR ALTER PROCEDURE lab_m04.publish_gold @batch_id varchar(80), @inject_fail_before_commit bit = 0
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        IF CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS varchar(100)) <> 'Latin1_General_100_BIN2_UTF8'
            THROW 51013, 'Confirmar collation binaria UTF8 antes da carga preparada.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_m04.stage_manifest) <> 1
            THROW 51000, 'Esperado um manifesto para o snapshot completo.', 1;
        IF NOT EXISTS (SELECT 1 FROM lab_m04.stage_manifest WHERE batch_id = @batch_id)
            THROW 51001, 'Batch nao corresponde ao manifesto.', 1;
        IF EXISTS (SELECT 1 FROM lab_m04.stage_manifest WHERE expected_rows <= 0 OR silver_delta_version < 0)
            THROW 51002, 'Manifesto vazio ou versao invalida.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_m04.stage_coleta) <> (SELECT expected_rows FROM lab_m04.stage_manifest)
            THROW 51003, 'Contagem de entrada diverge.', 1;
        IF (SELECT COUNT(DISTINCT cnpj) FROM lab_m04.stage_coleta) <> (SELECT expected_stations FROM lab_m04.stage_manifest)
            OR (SELECT COUNT(DISTINCT municipio_ibge) FROM lab_m04.stage_coleta) <> (SELECT expected_municipalities FROM lab_m04.stage_manifest)
            OR (SELECT SUM(CAST(preco_incomum_iqr AS bigint)) FROM lab_m04.stage_coleta) <> (SELECT expected_unusual FROM lab_m04.stage_manifest)
            THROW 51004, 'Cobertura ou sinal IQR diverge.', 1;
        IF EXISTS (SELECT 1 FROM lab_m04.stage_coleta WHERE produto <> 'GASOLINA' OR moeda <> 'BRL'
            OR unidade <> 'litro' OR uf <> 'RJ' OR preco_venda <= 0
            OR data_coleta < CAST('2026-01-01' AS date) OR data_coleta > CAST('2026-06-30' AS date))
            THROW 51005, 'Fatia fora do contrato M04 inicial.', 1;
        IF EXISTS (SELECT cnpj, produto, data_coleta, unidade FROM lab_m04.stage_coleta
            GROUP BY cnpj, produto, data_coleta, unidade HAVING COUNT_BIG(*) <> 1)
            THROW 51006, 'Chave de coleta duplicada.', 1;
        IF EXISTS (SELECT cnpj, data_coleta FROM (
            SELECT DISTINCT cnpj, data_coleta, revenda_observada, bandeira_observada, municipio_ibge, uf
            FROM lab_m04.stage_coleta) a GROUP BY cnpj, data_coleta HAVING COUNT_BIG(*) > 1)
            THROW 51007, 'Atributos ambiguos do posto na mesma data.', 1;
        IF EXISTS (SELECT data FROM lab_m04.dim_data GROUP BY data HAVING COUNT_BIG(*) <> 1)
            OR EXISTS (SELECT data_sk FROM lab_m04.dim_data GROUP BY data_sk HAVING COUNT_BIG(*) <> 1)
            OR EXISTS (SELECT municipio_ibge FROM lab_m04.dim_municipio GROUP BY municipio_ibge HAVING COUNT_BIG(*) <> 1)
            THROW 51008, 'Chaves de referencia duplicadas.', 1;
        IF EXISTS (SELECT 1 FROM lab_m04.stage_coleta s LEFT JOIN lab_m04.dim_data d ON s.data_coleta = d.data
            LEFT JOIN lab_m04.dim_municipio m ON s.municipio_ibge = m.municipio_ibge AND s.uf = m.uf
            WHERE d.data IS NULL OR m.municipio_ibge IS NULL)
            THROW 51009, 'Referencia dimensional ausente.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_m04.candidate_fato) <> (SELECT expected_rows FROM lab_m04.stage_manifest)
            THROW 51010, 'Associacao temporal nao reconciliou.', 1;
        IF EXISTS (SELECT 1 FROM lab_m04.candidate_posto a JOIN lab_m04.candidate_posto b
            ON a.cnpj = b.cnpj AND a.observado_desde < b.observado_desde
            AND (a.observado_ate IS NULL OR a.observado_ate > b.observado_desde))
            THROW 51011, 'Sobreposicao temporal.', 1;

        -- Substituição integral SOMENTE do laboratório, dentro da mesma transação Warehouse.
        DELETE FROM lab_m04.fato_preco_coletado;
        DELETE FROM lab_m04.dim_posto;
        DELETE FROM lab_m04.dim_produto;
        INSERT INTO lab_m04.dim_produto VALUES (1, 'GASOLINA', 'BRL', 'litro');
        INSERT INTO lab_m04.dim_posto SELECT * FROM lab_m04.candidate_posto;
        INSERT INTO lab_m04.fato_preco_coletado
            SELECT posto_sk, data_sk, produto_sk, municipio_ibge, cnpj_origem, municipio_origem,
                preco_venda, preco_incomum_iqr, @batch_id FROM lab_m04.candidate_fato;
        IF EXISTS (SELECT * FROM lab_m04.stage_business_bytes EXCEPT SELECT * FROM lab_m04.published_business_bytes)
            OR EXISTS (SELECT * FROM lab_m04.published_business_bytes EXCEPT SELECT * FROM lab_m04.stage_business_bytes)
            OR (SELECT COUNT_BIG(*) FROM lab_m04.business_published) <> (SELECT expected_rows FROM lab_m04.stage_manifest)
            THROW 51012, 'Negocio publicado diverge da Silver candidata.', 1;
        DELETE FROM lab_m04.publication;
        INSERT INTO lab_m04.publication
            SELECT batch_id, scope_id, source_sha256, ibge_sha256, silver_delta_version, is_synthetic,
                CAST(SYSUTCDATETIME() AS datetime2(6)), expected_rows, source_table, snapshot_id FROM lab_m04.stage_manifest;
        IF @inject_fail_before_commit = 1
            THROW 51999, 'Falha injetada apos escritas e antes do commit.', 1;
        COMMIT TRANSACTION;
        SELECT 'gold_lab_published' AS status, * FROM lab_m04.publication;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
