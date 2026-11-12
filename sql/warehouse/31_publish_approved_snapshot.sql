-- Executar depois de 30_import_approved_snapshot.sql. Não alterar parâmetros.
IF (SELECT COUNT_BIG(*) FROM gold.stage_manifest) <> 1
    THROW 51220, 'Importar um snapshot aprovado antes de publicar.', 1;
DECLARE @batch varchar(80) = (SELECT batch_id FROM gold.stage_manifest);
EXEC gold.publish_gold @batch_id=@batch;
