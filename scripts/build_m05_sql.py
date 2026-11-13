"""Compoe scripts M05 a partir do pacote M04 aceito; nao executa SQL."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/artifacts/m05/warehouse"
OUTPUT.mkdir(parents=True, exist_ok=True)
M04 = ROOT / "data/artifacts/m04_fabric/warehouse"
guard_tables = {"facts": "published_business_bytes", "posto": "dim_posto", "publication": "publication",
                "calendar": "dim_data", "municipios": "dim_municipio", "produtos": "dim_produto"}
schema_sql = (ROOT / "sql/warehouse/01_schema.sql").read_text(encoding="utf-8")


def guard_source(source):
    """Textos em bytes: EXCEPT nao pode ignorar espacos finais na prova de protecao."""
    if source == "published_business_bytes":
        return "gold.published_business_bytes"
    import re
    definition = re.search(r"CREATE TABLE lab_m04\." + source + r" \(([\s\S]*?)\n\);", schema_sql).group(1)
    fields = re.findall(r"(?:^|,)\s*([a-z_][a-z0-9_]*)\s+([a-z]+)\(", definition)
    # Campos int, bigint, bit e date nao possuem tamanho entre parenteses.
    names = re.findall(r"(?:^|,)\s*([a-z_][a-z0-9_]*)\s+(?:varchar|decimal|datetime2|int|bigint|bit|date)\b", definition)
    texts = {name for name, kind in fields if kind == "varchar"}
    columns = ",".join(f"CAST({name} AS varbinary(8000)) AS {name}" if name in texts else name for name in names)
    return f"(SELECT {columns} FROM gold.{source}) AS current_state"
root_parameter = """DECLARE @root varchar(36) = '{{ROOT_RUN_ID}}';
IF TRY_CONVERT(uniqueidentifier,@root) IS NULL
    THROW 51600, 'Pipeline RunId invalido.', 1;
"""
setup = """IF SCHEMA_ID('m05') IS NULL EXEC('CREATE SCHEMA m05');
IF OBJECT_ID('m05.attempt') IS NULL
CREATE TABLE m05.attempt (root_run_id varchar(36) NOT NULL, status varchar(30) NOT NULL,
    batch_id varchar(80) NULL, captured_at_utc datetime2(6) NOT NULL, completed_at_utc datetime2(6) NULL);
"""
for alias, source in guard_tables.items():
    setup += f"""IF OBJECT_ID('m05.guard_{alias}') IS NULL
CREATE TABLE m05.guard_{alias} AS SELECT CAST('' AS varchar(36)) AS root_run_id, *
FROM {guard_source(source)} WHERE 1=0;
"""
capture = root_parameter + """IF EXISTS (SELECT 1 FROM m05.attempt WHERE root_run_id=@root)
    THROW 51601, 'Nao sobrescrever baseline de uma tentativa existente.', 1;
BEGIN TRY
    BEGIN TRANSACTION;
    INSERT INTO m05.attempt VALUES (@root,'started',NULL,CAST(SYSUTCDATETIME() AS datetime2(6)),NULL);
"""
for alias, source in guard_tables.items():
    capture += f"    INSERT INTO m05.guard_{alias} SELECT @root,* FROM {guard_source(source)};\n"
capture += """    COMMIT TRANSACTION;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
SELECT 'm05_baseline_captured' AS status,@root AS root_run_id;
"""
unchanged = root_parameter + """IF NOT EXISTS (SELECT 1 FROM m05.attempt WHERE root_run_id=@root)
    THROW 51602, 'Baseline ausente.', 1;
"""
for alias, source in guard_tables.items():
    unchanged += f"""IF (SELECT COUNT_BIG(*) FROM m05.guard_{alias} WHERE root_run_id=@root)
       <> (SELECT COUNT_BIG(*) FROM {guard_source(source)})
    OR EXISTS (SELECT * FROM m05.guard_{alias} WHERE root_run_id=@root EXCEPT SELECT @root,* FROM {guard_source(source)})
    OR EXISTS (SELECT @root,* FROM {guard_source(source)} EXCEPT SELECT * FROM m05.guard_{alias} WHERE root_run_id=@root)
    THROW 51603, 'Publicacao anterior mudou: {alias}.', 1;
"""
unchanged += "SELECT 'm05_previous_publication_unchanged' AS status,@root AS root_run_id;\n"
import_sql = (M04 / "30_import_approved_snapshot.sql").read_text(encoding="utf-8").replace("COLAR_BATCH_ID_DO_NOTEBOOK_06", "{{BATCH_ID}}")
publish = root_parameter + """DECLARE @batch varchar(80) = '{{BATCH_ID}}';
DECLARE @fault varchar(20) = '{{FAULT_STAGE}}';
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
"""
validate = root_parameter + (M04 / "32_gold_validate.sql").read_text(encoding="utf-8") + """
IF NOT EXISTS (SELECT 1 FROM m05.attempt a JOIN gold.publication p ON a.batch_id=p.batch_id
    WHERE a.root_run_id=@root AND a.status='published')
    THROW 51605, 'Lote publicado nao corresponde a tentativa.', 1;
UPDATE m05.attempt SET status='validated',completed_at_utc=CAST(SYSUTCDATETIME() AS datetime2(6))
    WHERE root_run_id=@root;
SELECT 'm05_pipeline_validated' AS status,* FROM m05.attempt WHERE root_run_id=@root;
"""
for name, content in {"00_setup.sql": setup, "01_capture.sql": capture, "30_import.sql": import_sql,
                      "31_publish.sql": publish, "32_validate.sql": validate, "90_assert_unchanged.sql": unchanged}.items():
    (OUTPUT / name).write_text(content, encoding="utf-8")
print(json.dumps({"status": "m05_sql_prepared", "fabric_executed": False, "scripts": 6}))
