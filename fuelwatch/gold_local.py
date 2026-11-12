"""Ensaio relacional M04 em DuckDB; não é execução nem emulador do Fabric Warehouse."""

from datetime import date, timedelta
from pathlib import Path
import re

import duckdb
import pyarrow as pa

from fuelwatch.m02_reference import BUSINESS_FIELDS

ROOT = Path(__file__).resolve().parents[1]


def calendar(start, end):
    rows = []
    day = start
    while day <= end:
        iso = day.isocalendar()
        rows.append({"data_sk": int(day.strftime("%Y%m%d")), "data": day,
                     "inicio_semana_iso": day - timedelta(days=day.weekday()),
                     "ano_iso": iso.year, "semana_iso": iso.week})
        day += timedelta(days=1)
    return rows


def open_model():
    conn = duckdb.connect()
    conn.execute("CREATE SCHEMA lab_m04")
    conn.execute("CREATE MACRO DATALENGTH(x) AS octet_length(encode(x))")
    schema = (ROOT / "sql/warehouse/01_schema.sql").read_text(encoding="utf-8")
    for statement in re.findall(r"CREATE TABLE lab_m04\.\w+ \([\s\S]*?\n\);", schema):
        # Somente adaptações de tipos locais. IF/GO/procedure/transação T-SQL não são executados.
        statement = re.sub(r"\bbit\b", "BOOLEAN", statement, flags=re.I)
        statement = statement.replace("datetime2(6)", "TIMESTAMP")
        conn.execute(statement)
    core = (ROOT / "sql/warehouse/02_station_history.sql").read_text(encoding="utf-8")
    core = core.replace("CONVERT(varchar(10), data_coleta, 23)", "CAST(data_coleta AS varchar(10))")
    core = re.sub(r"CAST\((\w+) AS varbinary\(8000\)\)", r"encode(\1)", core)
    conn.execute(core.replace("COUNT_BIG(*)", "COUNT(*)"))
    return conn


def replace_rows(conn, name, rows):
    conn.execute(f"DELETE FROM lab_m04.{name}")
    if rows:
        table = pa.Table.from_pylist(rows)
        conn.register("incoming", table)
        conn.execute(f"INSERT INTO lab_m04.{name} BY NAME SELECT * FROM incoming")
        conn.unregister("incoming")


def load_input(conn, rows, municipalities):
    replace_rows(conn, "stage_coleta", [{k: r[k] for k in BUSINESS_FIELDS} for r in rows])
    replace_rows(conn, "dim_data", calendar(date(2026, 1, 1), date(2026, 6, 30)))
    replace_rows(conn, "dim_municipio", [{k: r[k] for k in ["municipio_ibge", "nome", "uf"]} for r in municipalities])


def publish_local(conn):
    """Valida cardinalidade e publica somente no banco DuckDB efêmero deste ensaio."""
    ambiguous = conn.execute("""SELECT COUNT(*) FROM (
        SELECT cnpj, data_coleta FROM (
            SELECT DISTINCT cnpj, data_coleta, revenda_observada, bandeira_observada, municipio_ibge, uf
            FROM lab_m04.stage_coleta) a GROUP BY cnpj, data_coleta HAVING COUNT(*) > 1) b""").fetchone()[0]
    duplicates = conn.execute("""SELECT COUNT(*) FROM (
        SELECT cnpj, produto, data_coleta, unidade FROM lab_m04.stage_coleta
        GROUP BY cnpj, produto, data_coleta, unidade HAVING COUNT(*) > 1) a""").fetchone()[0]
    bad_references = conn.execute("""SELECT COUNT(*) FROM lab_m04.stage_coleta s
        LEFT JOIN lab_m04.dim_data d ON s.data_coleta=d.data
        LEFT JOIN lab_m04.dim_municipio m ON s.municipio_ibge=m.municipio_ibge AND s.uf=m.uf
        WHERE d.data IS NULL OR m.municipio_ibge IS NULL""").fetchone()[0]
    if ambiguous or duplicates or bad_references:
        raise ValueError(f"Input blocked: ambiguous={ambiguous}, duplicates={duplicates}, missing_reference={bad_references}")
    count = conn.execute("SELECT COUNT(*) FROM lab_m04.stage_coleta").fetchone()[0]
    if not count or conn.execute("SELECT COUNT(*) FROM lab_m04.candidate_fato").fetchone()[0] != count:
        raise ValueError("Empty input or temporal mismatch")
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute("DELETE FROM lab_m04.fato_preco_coletado")
        conn.execute("DELETE FROM lab_m04.dim_posto")
        conn.execute("DELETE FROM lab_m04.dim_produto")
        conn.execute("INSERT INTO lab_m04.dim_produto VALUES (1, 'GASOLINA', 'BRL', 'litro')")
        conn.execute("INSERT INTO lab_m04.dim_posto SELECT * FROM lab_m04.candidate_posto")
        conn.execute("INSERT INTO lab_m04.fato_preco_coletado SELECT *, 'local-model' FROM lab_m04.candidate_fato")
        for a, b in [("stage_coleta", "business_published"), ("business_published", "stage_coleta")]:
            if conn.execute(f"SELECT COUNT(*) FROM (SELECT * FROM lab_m04.{a} EXCEPT ALL SELECT * FROM lab_m04.{b})").fetchone()[0]:
                raise ValueError("Business mismatch")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def typed_fixture():
    from fuelwatch.contract import classify_rows
    from fuelwatch.versioning_lab import LOOKUP, SCOPE, fixture_row

    raw = [fixture_row("05/01/2026", "6,00"), fixture_row("12/01/2026", "6,20"),
           fixture_row("19/01/2026", "6,40"), fixture_row("30/06/2026", "6,60")]
    for row in raw[2:]:
        row["Bandeira"] = "LAB B"
        row["Revenda"] = "LAB NOVO NOME"
    rows, invalid, duplicates, conflicts = classify_rows(list(enumerate(raw, 2)), LOOKUP, SCOPE)
    if invalid or duplicates or conflicts:
        raise ValueError("Fixture invalido")
    return [{**{k: r[k] for k in BUSINESS_FIELDS if k != "preco_incomum_iqr"}, "preco_incomum_iqr": False} for r in rows]
