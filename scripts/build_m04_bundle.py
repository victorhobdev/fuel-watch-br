"""Pacote executável M04: notebook de transferência, setup, fixtures e Gold oficial fixada."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import shutil

from fuelwatch.gold_local import load_input, open_model, publish_local
from fuelwatch.m02_reference import BUSINESS_FIELDS, decode_reference
from scripts.prepare_m04_gold import insert

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/artifacts/m04_fabric"
TEXT_FIELDS = {"posto_sk", "cnpj", "cnpj_origem", "produto", "moeda", "unidade", "uf", "municipio_ibge",
               "municipio_origem", "revenda_observada", "bandeira_observada"}
POSTO_FIELDS = ["posto_sk", "cnpj", "revenda_observada", "bandeira_observada", "municipio_ibge", "uf", "observado_desde", "observado_ate"]
WEEKLY_FIELDS = ["inicio_semana_iso", "ano_iso", "semana_iso", "municipio_ibge", "produto", "moeda", "unidade",
                 "coletas", "postos_observados", "soma_precos", "preco_minimo", "preco_maximo", "precos_incomuns"]


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def projection(fields):
    return ", ".join(f"CAST({f} AS varbinary(8000))" if f in TEXT_FIELDS else f for f in fields)


def difference(left, right, fields):
    columns = projection(fields)
    return f"EXISTS (SELECT {columns} FROM {left} EXCEPT SELECT {columns} FROM {right})"


def table_ddl(name, target):
    source = (ROOT / "sql/warehouse/01_schema.sql").read_text(encoding="utf-8")
    statement = re.search(r"CREATE TABLE lab_m04\." + name + r" \([\s\S]*?\n\);", source).group()
    return f"IF OBJECT_ID('{target}') IS NULL\n" + statement.replace("lab_m04." + name, target)


def setup(schema):
    ddl = (ROOT / "sql/warehouse/01_schema.sql").read_text(encoding="utf-8")
    ddl = f"-- M04: instalar objetos no schema {schema}, no Warehouse exclusivo do Fuel Watch BR.\n" + ddl[ddl.index("IF SCHEMA_ID"):]
    ddl = re.sub(r"(?m)^GO\s*$", "", ddl).replace("lab_m04", schema)
    ddl += "\n" + table_ddl("dim_posto", schema + ".expected_posto")
    if schema == "lab_m04":
        ddl += "\n" + table_ddl("stage_coleta", "lab_m04.expected_coleta")
        ddl += """\nIF OBJECT_ID('lab_m04.fixture_checks') IS NULL
CREATE TABLE lab_m04.fixture_checks (experiment_id varchar(36), scenario varchar(100), status varchar(50),
    observations bigint, station_versions bigint, checked_at_utc datetime2(6));\n"""
    else:
        ddl += """\nIF OBJECT_ID('gold.expected_weekly') IS NULL
CREATE TABLE gold.expected_weekly (
    inicio_semana_iso date, ano_iso int, semana_iso int, municipio_ibge varchar(7), produto varchar(80),
    moeda varchar(3), unidade varchar(30), coletas bigint, postos_observados bigint,
    soma_precos decimal(38,3), preco_minimo decimal(10,3), preco_maximo decimal(10,3), precos_incomuns bigint
);\n"""
    core = (ROOT / "sql/warehouse/02_station_history.sql").read_text(encoding="utf-8")
    views = re.findall(r"CREATE VIEW lab_m04\.[\s\S]*?;", core)
    if len(views) != 6:
        raise ValueError("Esperadas seis views no modelo")
    procedure = (ROOT / "sql/warehouse/03_publish_gold.sql").read_text(encoding="utf-8")
    procedure = procedure[procedure.index("CREATE OR ALTER PROCEDURE"):]
    if schema == "gold":
        procedure = procedure.replace("gold_lab_published", "gold_published")
        procedure = procedure.replace("SOMENTE do laboratório", "SOMENTE desta fatia oficial")
        marker = "        IF EXISTS (SELECT 1 FROM lab_m04.stage_manifest WHERE expected_rows <= 0"
        guard = """        IF EXISTS (SELECT 1 FROM lab_m04.stage_manifest WHERE is_synthetic <> 0
            OR scope_id <> 'anp-2026-1-rj-gasolina' OR silver_delta_version < 0
            OR source_table <> 'silver_preco_publicado' OR TRY_CONVERT(uniqueidentifier,snapshot_id) IS NULL)
            THROW 51230, 'Gold oficial exige baseline aprovado nao sintetico.', 1;
"""
        procedure = procedure.replace(marker, guard + marker)
    for statement in views + [procedure]:
        statement = statement.replace("CREATE VIEW ", "CREATE OR ALTER VIEW ", 1).replace("lab_m04", schema)
        # Cada DDL fica no próprio batch dinâmico; o usuário não precisa recortar views nem usar GO.
        ddl += "\nEXEC(N'" + statement.replace("'", "''") + "');\n"
    label = "lab" if schema == "lab_m04" else "gold"
    ddl += f"SELECT 'm04_{label}_setup_ready' AS status, DB_NAME() AS warehouse_name;\n"
    return ddl


def fixture_suite(artifact, municipalities):
    names = ["10_base", "10_base", "11_late_attribute", "12_corrected_attribute", "13_price_only",
             "14_rejected_conflict", "13_price_only"]
    labels = ["base", "replay", "late_attribute", "attribute_correction", "price_only", "rejected_conflict", "rollback_after_writes"]
    body = "-- Executar integralmente: sete cenarios; rejeicoes esperadas sao capturadas.\nDECLARE @experiment_id varchar(36)=CONVERT(varchar(36),NEWID());\n"
    conn = open_model()
    previous_rows = None
    previous_control = None
    try:
        for index, (name, label) in enumerate(zip(names, labels)):
            rows = json.loads((artifact / (name + ".json")).read_text(encoding="utf-8"))
            for row in rows:
                row["data_coleta"] = date.fromisoformat(row["data_coleta"])
                row["preco_venda"] = Decimal(row["preco_venda"])
            if label == "rollback_after_writes":
                rows[0]["preco_venda"] = Decimal("7.100")
            control = {"batch_id": "lab-m04-" + label, "scope_id": "lab_m04_2026_1_rj_gasolina",
                       "source_sha256": sha(json.dumps(rows, default=str, sort_keys=True).encode()),
                       "ibge_sha256": "2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0",
                       "silver_delta_version": 0, "is_synthetic": True, "expected_rows": len(rows),
                       "expected_stations": 1, "expected_municipalities": 1, "expected_unusual": 0,
                       "source_table": "lab_m04_fixture", "snapshot_id": "fixture-" + label}
            body += f"\n-- {index + 1}: {label}\nBEGIN TRANSACTION;\nDELETE FROM lab_m04.stage_coleta;\nDELETE FROM lab_m04.stage_manifest;\n"
            body += insert("stage_coleta", rows, BUSINESS_FIELDS) + "\n"
            body += insert("stage_manifest", [control], list(control)) + "\nCOMMIT TRANSACTION;\n"
            error = 51006 if label == "rejected_conflict" else 51999 if label == "rollback_after_writes" else None
            invocation = f"EXEC lab_m04.publish_gold @batch_id='{control['batch_id']}', @inject_fail_before_commit={int(label == 'rollback_after_writes')};\n"
            if error:
                body += "BEGIN TRY\n" + invocation + "THROW 51400, 'O teste deveria ter falhado.', 1;\nEND TRY\nBEGIN CATCH\n"
                body += f"IF ERROR_NUMBER() <> {error} THROW;\nEND CATCH;\n"
            else:
                body += invocation
                load_input(conn, rows, municipalities)
                publish_local(conn)
                previous_rows, previous_control = deepcopy(rows), control
            history = conn.execute("SELECT * FROM lab_m04.dim_posto ORDER BY posto_sk").fetchall()
            expected_history = [dict(zip(POSTO_FIELDS, row)) for row in history]
            body += "DELETE FROM lab_m04.expected_coleta;\nDELETE FROM lab_m04.expected_posto;\n"
            body += insert("expected_coleta", previous_rows, BUSINESS_FIELDS) + "\n"
            body += insert("expected_posto", expected_history, POSTO_FIELDS) + "\n"
            errors = [difference("lab_m04.business_published", "lab_m04.expected_coleta", BUSINESS_FIELDS),
                      difference("lab_m04.expected_coleta", "lab_m04.business_published", BUSINESS_FIELDS),
                      difference("lab_m04.dim_posto", "lab_m04.expected_posto", POSTO_FIELDS),
                      difference("lab_m04.expected_posto", "lab_m04.dim_posto", POSTO_FIELDS)]
            body += "IF " + " OR ".join(errors) + f"\n    THROW 51401, 'Estado inesperado no cenario {label}.', 1;\n"
            body += f"IF (SELECT COUNT_BIG(*) FROM lab_m04.fato_preco_coletado) <> {len(previous_rows)} OR (SELECT COUNT_BIG(*) FROM lab_m04.dim_posto) <> {len(history)}\n"
            body += f"    THROW 51402, 'Multiplicidades inesperadas em {label}.', 1;\n"
            body += f"IF NOT EXISTS (SELECT 1 FROM lab_m04.publication WHERE batch_id='{previous_control['batch_id']}')\n    THROW 51403, 'Publicacao anterior nao preservada.', 1;\n"
            body += f"INSERT INTO lab_m04.fixture_checks VALUES (@experiment_id, '{label}', 'verified', {len(previous_rows)}, {len(history)}, CAST(SYSUTCDATETIME() AS datetime2(6)));\n"
        # A última candidata era a falha injetada; restaurar o stage válido sem repúblicar.
        body += "DELETE FROM lab_m04.stage_coleta;\nDELETE FROM lab_m04.stage_manifest;\n"
        body += insert("stage_coleta", previous_rows, BUSINESS_FIELDS) + "\n"
        body += insert("stage_manifest", [previous_control], list(previous_control)) + "\n"
        body += "SELECT 'm04_fixture_suite_validated' AS status, @experiment_id AS experiment_id, COUNT_BIG(*) AS scenarios_verified FROM lab_m04.fixture_checks WHERE experiment_id=@experiment_id HAVING COUNT_BIG(*)=7;\nSELECT * FROM lab_m04.fixture_checks WHERE experiment_id=@experiment_id ORDER BY checked_at_utc;\n"
    finally:
        conn.close()
    return body


def official_report():
    checks = [difference("gold.dim_posto", "gold.expected_posto", POSTO_FIELDS),
              difference("gold.expected_posto", "gold.dim_posto", POSTO_FIELDS),
              difference("gold.preco_semanal", "gold.expected_weekly", WEEKLY_FIELDS),
              difference("gold.expected_weekly", "gold.preco_semanal", WEEKLY_FIELDS)]
    checks += [difference("gold.business_published", "gold.stage_coleta", BUSINESS_FIELDS),
               difference("gold.stage_coleta", "gold.business_published", BUSINESS_FIELDS)]
    sql = "IF " + " OR ".join(checks) + "\n    THROW 51500, 'Gold diverge da referencia integral.', 1;\n"
    sql += """IF (SELECT COUNT_BIG(*) FROM gold.business_published) <> 8052
    OR (SELECT COUNT_BIG(*) FROM gold.dim_posto) <> 518 OR (SELECT COUNT_BIG(*) FROM gold.preco_semanal) <> 656
    OR (SELECT SUM(coletas) FROM gold.preco_semanal) <> 8052
    OR (SELECT SUM(soma_precos) FROM gold.preco_semanal) <> CAST(52777.200 AS decimal(38,3))
    OR (SELECT COUNT_BIG(*) FROM gold.publication) <> 1
    THROW 51501, 'Contagens ou publicacao nao reconciliam.', 1;
IF (SELECT COUNT(DISTINCT cnpj) FROM gold.business_published) <> 502
    OR (SELECT COUNT(DISTINCT municipio_ibge) FROM gold.business_published) <> 27
    OR (SELECT SUM(CAST(preco_incomum_iqr AS bigint)) FROM gold.business_published) <> 26
    THROW 51502, 'Cobertura ou precos incomuns divergiram.', 1;
IF EXISTS (SELECT 1 FROM gold.fato_preco_coletado f JOIN gold.dim_posto p ON f.posto_sk=p.posto_sk
    JOIN gold.dim_data d ON f.data_sk=d.data_sk WHERE d.data < p.observado_desde
    OR (p.observado_ate IS NOT NULL AND d.data >= p.observado_ate))
    THROW 51503, 'Associacao temporal invalida.', 1;
IF EXISTS (SELECT 1 FROM gold.preco_semanal
    WHERE ABS(preco_medio - soma_precos / CAST(coletas AS decimal(18,0))) > CAST(0.000001 AS decimal(10,6)))
    THROW 51504, 'Media semanal nao reconciliou.', 1;
IF EXISTS (SELECT 1 FROM gold.dim_data WHERE semana_iso <> DATEPART(ISO_WEEK, data)
    OR ano_iso <> YEAR(DATEADD(day,3,inicio_semana_iso))
    OR data_sk <> YEAR(data)*10000+MONTH(data)*100+DAY(data)
    OR DATEDIFF(day,CAST('1900-01-01' AS date),inicio_semana_iso) % 7 <> 0
    OR data < inicio_semana_iso OR data >= DATEADD(day,7,inicio_semana_iso))
    THROW 51505, 'Calendario ISO invalido.', 1;
SELECT 'm04_gold_snapshot_validated' AS status, batch_id, scope_id, source_table, snapshot_id, source_sha256, ibge_sha256,
    silver_delta_version, is_synthetic, rows_published AS observations,
    502 AS stations, 27 AS municipalities, 26 AS unusual_prices, 518 AS station_versions,
    656 AS weekly_groups, 13 AS business_columns_compared, CAST(1 AS bit) AS full_row_comparison_passed,
    CAST(SYSUTCDATETIME() AS datetime2(6)) AS checked_at_utc
FROM gold.publication FOR JSON PATH, WITHOUT_ARRAY_WRAPPER;
"""
    return sql


def build_bundle(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    upload = output / "upload"
    sql = output / "warehouse"
    upload.mkdir(exist_ok=True)
    sql.mkdir(exist_ok=True)
    proof = json.loads((ROOT / "evidence/m04/local-gold.json").read_text(encoding="utf-8"))
    artifact = ROOT / proof["artifacts"]
    for name, digest in proof["prepared_sql_sha256"].items():
        if sha((ROOT / name).read_bytes()) != digest:
            raise ValueError("SQL mudou apos ensaio local; executar prepare_m04_gold novamente: " + name)
    for source, target in [(ROOT / "data/artifacts/m02/fuelwatch_rules.zip", "fuelwatch_rules.zip"),
                           (ROOT / "data/artifacts/m02/reference.parquet", "reference.parquet"),
                           (ROOT / "data/artifacts/m02/municipios-rj.http.gz", "municipios-rj.http.gz"),
                           (artifact / "real_station_history.parquet", "expected_history.parquet"),
                           (artifact / "real_weekly.parquet", "expected_weekly.parquet")]:
        if source.name in proof["oracle_parquet_sha256"] and sha(source.read_bytes()) != proof["oracle_parquet_sha256"][source.name]:
            raise ValueError("Oracle local alterado apos verificacao: " + source.name)
        shutil.copyfile(source, upload / target)
    baseline = json.loads((ROOT / "data/artifacts/m02/manifest.json").read_text(encoding="utf-8"))
    for name, spec in baseline["files"].items():
        if sha((upload / name).read_bytes()) != spec["sha256"]:
            raise ValueError("Insumo M02 divergiu: " + name)
    municipalities, _ = decode_reference((upload / "municipios-rj.http.gz").read_bytes(), proof["ibge_sha256"])
    seed_body = (artifact / "05_seed_reference.sql").read_text(encoding="utf-8")
    seed = """BEGIN TRY
BEGIN TRANSACTION;
IF (SELECT COUNT_BIG(*) FROM lab_m04.dim_data)=0 AND (SELECT COUNT_BIG(*) FROM lab_m04.dim_municipio)=0
BEGIN
""" + seed_body + """
END;
IF (SELECT COUNT_BIG(*) FROM lab_m04.dim_data)<>181 OR (SELECT COUNT_BIG(*) FROM lab_m04.dim_municipio)<>92
    THROW 51410, 'Referencia parcial: investigar antes de prosseguir.', 1;
COMMIT TRANSACTION;
SELECT 'm04_reference_ready' AS status, 181 AS calendar_days, 92 AS municipalities;
END TRY
BEGIN CATCH
IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
THROW;
END CATCH;
"""
    (sql / "00_preflight.sql").write_text("""SELECT DB_NAME() AS item_name, CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS varchar(100)) AS collation_name;
IF CAST(DATABASEPROPERTYEX(DB_NAME(), 'Collation') AS varchar(100)) <> 'Latin1_General_100_BIN2_UTF8'
    THROW 51290, 'Parar: roteiro preparado para collation binaria UTF8.', 1;
""", encoding="utf-8")
    for name, content in [("01_lab_setup.sql", setup("lab_m04")),
                          ("02_lab_seed.sql", seed),
                          ("03_lab_fixture_suite.sql", fixture_suite(artifact, municipalities)),
                          ("04_lab_reconcile.sql", (ROOT / "sql/warehouse/04_reconcile.sql").read_text(encoding="utf-8")),
                          ("20_gold_setup.sql", setup("gold")), ("32_gold_validate.sql", official_report())]:
        (sql / name).write_text(content, encoding="utf-8")
    for name in ["30_import_approved_snapshot.sql", "31_publish_approved_snapshot.sql"]:
        shutil.copyfile(ROOT / "sql/warehouse" / name, sql / name)
    expected_files = {"fuelwatch_rules.zip", "reference.parquet", "municipios-rj.http.gz", "expected_history.parquet", "expected_weekly.parquet"}
    if {p.name for p in upload.iterdir()} - {"manifest.json"} != expected_files:
        raise ValueError("Pasta de upload tem arquivos inesperados; revisar antes de empacotar")
    manifest = {"bundle_version": "m04-v2", "source_sha256": proof["source_sha256"], "ibge_sha256": proof["ibge_sha256"],
                "scope": baseline["scope"], "source_table": "silver_preco_publicado",
                "delta_version_strategy": "successful_m03_consumer_contract", "official_republication_promoted": False,
                "files": {p.name: {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
                          for p in sorted(upload.iterdir()) if p.name != "manifest.json"},
                "warehouse_files": {p.name: sha(p.read_bytes()) for p in sorted(sql.glob("*.sql"))}}
    payload = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    (upload / "manifest.json").write_bytes(payload)
    return manifest, sha(payload)


def build_notebook(fingerprint):
    def cell(kind, source):
        value = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
        if kind == "code":
            value.update(execution_count=None, outputs=[])
        return value
    cells = [cell("markdown", "# M04 — Snapshot oficial selecionado no M03 para Warehouse\n\nPREPARADO; ainda não executado no Fabric.\nConcluir notebook 06 de seleção oficial M03 e parar sua sessão.\nAnexar lh_fuelwatch como default Lakehouse e usar sessão nova.\nEnviar os seis arquivos de data/artifacts/m04_fabric/upload para Files/m04_input.\nExecutar Run all; enviar o JSON m04_transfer_ready e parar a sessão.\nConsome o consumer_contract M03, fixa a versão publicada e reconcilia o baseline revisado.\nGrava apenas m04_transfer_* e arquivos de auditoria.\n"),
             cell("code", 'p_bundle_dir = "/lakehouse/default/Files/m04_input"\n' + f'p_expected_manifest_sha256 = "{fingerprint}"\n' + 'p_rules_library_path = ""\n'),
             cell("code", (ROOT / "notebooks/m04_sources/bootstrap.py").read_text(encoding="utf-8")),
             cell("code", (ROOT / "fuelwatch/gold_input.py").read_text(encoding="utf-8")),
             cell("code", (ROOT / "notebooks/m04_sources/07_export_gold_input.py").read_text(encoding="utf-8"))]
    cells[1]["metadata"]["tags"] = ["parameters"]
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Synapse PySpark", "name": "synapse_pyspark", "language": "python"},
                                            "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 4}
    path = ROOT / "notebooks/07_export_gold_input.ipynb"
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    manifest, fingerprint = build_bundle()
    notebook = build_notebook(fingerprint)
    print(json.dumps({"status": "m04_execution_package_prepared_not_fabric_validated", "manifest_sha256": fingerprint,
                      "upload_files": len(manifest["files"]) + 1, "sql_files": list(manifest["warehouse_files"]),
                      "notebook": notebook.relative_to(ROOT).as_posix()}))
