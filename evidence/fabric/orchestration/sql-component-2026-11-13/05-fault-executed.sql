DECLARE @root varchar(36) = '9b58a7fd-f29a-4d26-b807-e1045f95528a';
IF TRY_CONVERT(uniqueidentifier,@root) IS NULL
    THROW 51600, 'Pipeline RunId invalido.', 1;
DECLARE @batch varchar(80) = '4ef52958-b66b-40de-92df-68da53783740';
DECLARE @fault varchar(20) = 'gold';
IF TRY_CONVERT(uniqueidentifier,@batch) IS NULL OR @fault NOT IN ('none','silver','gold')
    THROW 51604, 'Parametros de publicacao invalidos.', 1;
IF NOT EXISTS (SELECT 1 FROM m05.attempt WHERE root_run_id=@root)
    THROW 51602, 'Baseline ausente.', 1;
DECLARE @inject bit = CASE WHEN @fault='gold' THEN 1 ELSE 0 END;
BEGIN TRY
    EXEC gold.publish_gold @batch_id=@batch,@inject_fail_before_commit=@inject;
    UPDATE m05.attempt SET status='published',batch_id=@batch WHERE root_run_id=@root;
END TRY
BEGIN CATCH
    UPDATE m05.attempt SET status='gold_failed',batch_id=@batch WHERE root_run_id=@root;
    THROW;
END CATCH;
