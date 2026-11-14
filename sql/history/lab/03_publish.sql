-- Publicacao nacional transacional; uma tentativa por vez.
CREATE OR ALTER PROCEDURE lab_gold_hist.publish_gold @batch_id varchar(80), @inject_fail_before_commit bit = 0
AS
BEGIN
    SET NOCOUNT ON;
    BEGIN TRY
        BEGIN TRANSACTION;
        DELETE FROM lab_gold_hist.dim_data;
        INSERT INTO lab_gold_hist.dim_data
            SELECT CAST(data_sk AS int),CAST(data AS date),CAST(inicio_semana_iso AS date),CAST(ano_iso AS int),CAST(semana_iso AS int)
            FROM lh_fuelwatch.dbo.lab_hist_transfer_calendar WHERE run_id=@batch_id;
        DELETE FROM lab_gold_hist.dim_municipio;
        INSERT INTO lab_gold_hist.dim_municipio SELECT municipio_ibge,nome,uf FROM lh_fuelwatch.dbo.lab_hist_transfer_municipio WHERE run_id=@batch_id;
        DELETE FROM lab_gold_hist.dim_produto;
        INSERT INTO lab_gold_hist.dim_produto SELECT CAST(DENSE_RANK() OVER (ORDER BY produto,moeda,unidade) AS int),produto,moeda,unidade
            FROM (SELECT DISTINCT produto,moeda,unidade FROM lab_gold_hist.stage_coleta) p;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.dim_data)<>(SELECT expected_calendar_days FROM lab_gold_hist.stage_manifest) OR (SELECT COUNT_BIG(*) FROM lab_gold_hist.dim_produto)<>(SELECT expected_products FROM lab_gold_hist.stage_manifest)
            THROW 51806, 'Dimensoes nacionais incompletas.', 1;

        IF CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS varchar(100)) <> 'Latin1_General_100_BIN2_UTF8'
            THROW 51013, 'Confirmar collation binaria UTF8 antes da carga preparada.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.stage_manifest) <> 1
            THROW 51000, 'Esperado um manifesto para o snapshot completo.', 1;
        IF NOT EXISTS (SELECT 1 FROM lab_gold_hist.stage_manifest WHERE batch_id = @batch_id)
            THROW 51001, 'Batch nao corresponde ao manifesto.', 1;
        IF EXISTS (SELECT 1 FROM lab_gold_hist.stage_manifest WHERE expected_rows <= 0 OR silver_delta_version < 0)
            THROW 51002, 'Manifesto vazio ou versao invalida.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.stage_coleta) <> (SELECT expected_rows FROM lab_gold_hist.stage_manifest)
            THROW 51003, 'Contagem de entrada diverge.', 1;
        IF (SELECT COUNT(DISTINCT cnpj) FROM lab_gold_hist.stage_coleta) <> (SELECT expected_stations FROM lab_gold_hist.stage_manifest)
            OR (SELECT COUNT(DISTINCT municipio_ibge) FROM lab_gold_hist.stage_coleta) <> (SELECT expected_municipalities FROM lab_gold_hist.stage_manifest)
            OR (SELECT SUM(CAST(preco_incomum_iqr AS bigint)) FROM lab_gold_hist.stage_coleta) <> (SELECT expected_unusual FROM lab_gold_hist.stage_manifest)
            THROW 51004, 'Cobertura ou sinal IQR diverge.', 1;
        IF EXISTS (SELECT 1 FROM lab_gold_hist.stage_coleta s LEFT JOIN lab_gold_hist.dim_produto r
            ON s.produto=r.produto AND s.moeda=r.moeda AND s.unidade=r.unidade
            WHERE r.produto_sk IS NULL OR s.preco_venda<=0 OR s.data_coleta<(SELECT date_start FROM lab_gold_hist.stage_manifest) OR s.data_coleta>(SELECT date_end FROM lab_gold_hist.stage_manifest))
            THROW 51805, 'Produto/unidade/periodo nacional invalido.', 1;
        IF EXISTS (SELECT cnpj, produto, data_coleta, unidade FROM lab_gold_hist.stage_coleta
            GROUP BY cnpj, produto, data_coleta, unidade HAVING COUNT_BIG(*) <> 1)
            THROW 51006, 'Chave de coleta duplicada.', 1;
        IF EXISTS (SELECT cnpj, data_coleta FROM (
            SELECT DISTINCT cnpj, data_coleta, revenda_observada, bandeira_observada, municipio_ibge, uf
            FROM lab_gold_hist.stage_coleta) a GROUP BY cnpj, data_coleta HAVING COUNT_BIG(*) > 1)
            THROW 51007, 'Atributos ambiguos do posto na mesma data.', 1;
        IF EXISTS (SELECT data FROM lab_gold_hist.dim_data GROUP BY data HAVING COUNT_BIG(*) <> 1)
            OR EXISTS (SELECT data_sk FROM lab_gold_hist.dim_data GROUP BY data_sk HAVING COUNT_BIG(*) <> 1)
            OR EXISTS (SELECT municipio_ibge FROM lab_gold_hist.dim_municipio GROUP BY municipio_ibge HAVING COUNT_BIG(*) <> 1)
            THROW 51008, 'Chaves de referencia duplicadas.', 1;
        IF EXISTS (SELECT 1 FROM lab_gold_hist.stage_coleta s LEFT JOIN lab_gold_hist.dim_data d ON s.data_coleta = d.data
            LEFT JOIN lab_gold_hist.dim_municipio m ON s.municipio_ibge = m.municipio_ibge AND s.uf = m.uf
            WHERE d.data IS NULL OR m.municipio_ibge IS NULL)
            THROW 51009, 'Referencia dimensional ausente.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.candidate_fato) <> (SELECT expected_rows FROM lab_gold_hist.stage_manifest)
            THROW 51010, 'Associacao temporal nao reconciliou.', 1;
        IF EXISTS (SELECT 1 FROM lab_gold_hist.candidate_posto a JOIN lab_gold_hist.candidate_posto b
            ON a.cnpj = b.cnpj AND a.observado_desde < b.observado_desde
            AND (a.observado_ate IS NULL OR a.observado_ate > b.observado_desde))
            THROW 51011, 'Sobreposicao temporal.', 1;

        -- Substituição integral SOMENTE do laboratório, dentro da mesma transação Warehouse.
        DELETE FROM lab_gold_hist.fato_preco_coletado;
        DELETE FROM lab_gold_hist.dim_posto;
        INSERT INTO lab_gold_hist.dim_posto SELECT * FROM lab_gold_hist.candidate_posto;
        INSERT INTO lab_gold_hist.fato_preco_coletado
            SELECT posto_sk, data_sk, produto_sk, municipio_ibge, cnpj_origem, municipio_origem,
                preco_venda, preco_incomum_iqr, @batch_id FROM lab_gold_hist.candidate_fato;
        IF EXISTS (SELECT * FROM lab_gold_hist.stage_business_bytes EXCEPT SELECT * FROM lab_gold_hist.published_business_bytes)
            OR EXISTS (SELECT * FROM lab_gold_hist.published_business_bytes EXCEPT SELECT * FROM lab_gold_hist.stage_business_bytes)
            OR (SELECT COUNT_BIG(*) FROM lab_gold_hist.business_published) <> (SELECT expected_rows FROM lab_gold_hist.stage_manifest)
            THROW 51012, 'Negocio publicado diverge da Silver candidata.', 1;
        DELETE FROM lab_gold_hist.publication;
        INSERT INTO lab_gold_hist.publication
            SELECT batch_id, scope_id, source_sha256, ibge_sha256, silver_delta_version, is_synthetic,
                CAST(SYSUTCDATETIME() AS datetime2(6)), expected_rows, source_table, snapshot_id FROM lab_gold_hist.stage_manifest;

        IF EXISTS (SELECT source_id FROM lab_gold_hist.stage_source_versions GROUP BY source_id HAVING COUNT_BIG(*)<>1)
            THROW 51830,'Mais de uma versao ativa para o mesmo arquivo.',1;
        IF (SELECT SUM(accepted_rows) FROM lab_gold_hist.stage_source_versions)<>(SELECT expected_rows FROM lab_gold_hist.stage_manifest)
            THROW 51831,'Versoes nao reconciliam com as coletas.',1;
        IF EXISTS (SELECT 1 FROM lab_gold_hist.stage_source_versions a JOIN lab_gold_hist.stage_source_versions b
            ON a.source_id<b.source_id AND a.date_start<=b.date_end AND b.date_start<=a.date_end)
            THROW 51832,'Periodos de arquivos ativos se sobrepoem.',1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.dim_data d JOIN lab_gold_hist.stage_source_versions v ON d.data BETWEEN v.date_start AND v.date_end)
            <>(SELECT expected_calendar_days FROM lab_gold_hist.stage_manifest)
            THROW 51833,'Arquivos ativos nao cobrem o calendario contratado.',1;
        DELETE FROM lab_gold_hist.source_versions;
        INSERT INTO lab_gold_hist.source_versions SELECT * FROM lab_gold_hist.stage_source_versions;
        IF @inject_fail_before_commit = 1
            THROW 51999, 'Falha injetada apos escritas e antes do commit.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.dim_posto)<>(SELECT COUNT_BIG(*) FROM lab_gold_hist.expected_posto)
            OR EXISTS (SELECT * FROM lab_gold_hist.dim_posto EXCEPT SELECT * FROM lab_gold_hist.expected_posto)
            OR EXISTS (SELECT * FROM lab_gold_hist.expected_posto EXCEPT SELECT * FROM lab_gold_hist.dim_posto)
            THROW 51807, 'Historico nacional diverge da referencia independente.', 1;
        IF EXISTS (SELECT * FROM lab_gold_hist.stage_business_bytes EXCEPT SELECT * FROM lab_gold_hist.published_business_bytes)
            OR EXISTS (SELECT * FROM lab_gold_hist.published_business_bytes EXCEPT SELECT * FROM lab_gold_hist.stage_business_bytes)
            THROW 51808, 'Negocio nacional divergiu depois dos joins dimensionais.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.fato_preco_coletado)<>(SELECT COUNT_BIG(*) FROM lab_gold_hist.stage_coleta)
            THROW 51809, 'Associacao nacional alterou cardinalidade.', 1;
        IF (SELECT COUNT_BIG(*) FROM lab_gold_hist.preco_semanal)<>(SELECT COUNT_BIG(*) FROM lab_gold_hist.expected_weekly)
            OR EXISTS (SELECT inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns FROM lab_gold_hist.preco_semanal EXCEPT SELECT * FROM lab_gold_hist.expected_weekly)
            OR EXISTS (SELECT * FROM lab_gold_hist.expected_weekly EXCEPT SELECT inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns FROM lab_gold_hist.preco_semanal)
            THROW 51810, 'Agregacao nacional diverge da referencia independente.', 1;
        COMMIT TRANSACTION;
        SELECT 'historical_gold_published' AS status, * FROM lab_gold_hist.publication;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW;
    END CATCH;
END;
