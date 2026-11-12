"""Ensaia Gold local com o snapshot real e gera entradas sintéticas T-SQL isoladas."""

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import duckdb
import pyarrow.parquet as pq

from fuelwatch.gold_local import calendar, load_input, open_model, publish_local, typed_fixture
from fuelwatch.m02_reference import BUSINESS_FIELDS, decode_reference

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def literal(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, Decimal)):
        return str(value)
    if isinstance(value, date):
        return "CAST('" + value.isoformat() + "' AS date)"
    return "'" + str(value).replace("'", "''") + "'"


def insert(table, rows, fields):
    # Lotes pequenos para não depender do limite de construtores VALUES do destino.
    return "\n".join("INSERT INTO lab_m04." + table + " (" + ", ".join(fields) + ") VALUES\n" +
                     ",\n".join("(" + ", ".join(literal(r[f]) for f in fields) + ")" for r in rows[i:i+100]) + ";"
                     for i in range(0, len(rows), 100))


def main():
    run_id = str(uuid4())
    out = ROOT / "data/artifacts/m04" / run_id
    out.mkdir(parents=True, exist_ok=False)
    proof = json.loads((ROOT / "evidence/local-slice.json").read_text(encoding="utf-8"))
    manifest_bytes = (ROOT / "data/artifacts/m02/manifest.json").read_bytes()
    preparation = json.loads((ROOT / "evidence/m02/preparation.json").read_text(encoding="utf-8"))
    if hashlib.sha256(manifest_bytes).hexdigest() != preparation["bundle_manifest_sha256"]:
        raise ValueError("Manifesto M02 diferente do aprovado")
    manifest = json.loads(manifest_bytes)
    for name, spec in manifest["files"].items():
        if hashlib.sha256((ROOT / "data/artifacts/m02" / name).read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError("Arquivo M02 diferente do aprovado: " + name)
    reference = pq.read_table(ROOT / "data/artifacts/m02/reference.parquet")
    rows = reference.to_pylist()
    municipalities, _ = decode_reference((ROOT / "data/artifacts/m02/municipios-rj.http.gz").read_bytes(), proof["ibge_sha256"])
    widths = {"cnpj": 14, "cnpj_origem": 80, "produto": 80, "moeda": 3, "unidade": 30, "uf": 2,
              "municipio_ibge": 7, "municipio_origem": 200, "revenda_observada": 1000, "bandeira_observada": 300}
    max_bytes = {field: max(len(r[field].encode("utf-8")) for r in rows) for field in widths}
    if any(max_bytes[field] > limit for field, limit in widths.items()):
        raise ValueError("Texto ultrapassa largura UTF8 do stage; revisar DDL antes de copiar")
    conn = open_model()
    try:
        load_input(conn, rows, municipalities)
        publish_local(conn)
        history = conn.execute("SELECT * FROM lab_m04.dim_posto ORDER BY posto_sk").fetchall()
        published = conn.execute("SELECT * FROM lab_m04.business_published ORDER BY cnpj, data_coleta").fetchall()
        before = hashlib.sha256(json.dumps([history, published], default=str, ensure_ascii=False).encode()).hexdigest()
        publish_local(conn)
        repeated = [conn.execute("SELECT * FROM lab_m04.dim_posto ORDER BY posto_sk").fetchall(),
                    conn.execute("SELECT * FROM lab_m04.business_published ORDER BY cnpj, data_coleta").fetchall()]
        after = hashlib.sha256(json.dumps(repeated, default=str, ensure_ascii=False).encode()).hexdigest()
        if before != after:
            raise ValueError("Repeticao local alterou Gold")
        metrics = conn.execute("""SELECT COUNT(*), COUNT(DISTINCT cnpj), COUNT(DISTINCT municipio_ibge),
            SUM(CAST(preco_incomum_iqr AS int)) FROM lab_m04.business_published""").fetchone()
        if metrics != (8052, 502, 27, 26):
            raise ValueError("Cobertura nao reconciliou")
        multiple_flags = conn.execute("""SELECT COUNT(*) FROM (SELECT cnpj FROM lab_m04.stage_coleta
            GROUP BY cnpj HAVING COUNT(DISTINCT bandeira_observada) > 1) a""").fetchone()[0]
        multi_version_stations = conn.execute("""SELECT COUNT(*) FROM (SELECT cnpj FROM lab_m04.dim_posto
            GROUP BY cnpj HAVING COUNT(*) > 1) a""").fetchone()[0]
        changed_attributes = {}
        for field in ["revenda_observada", "bandeira_observada", "municipio_ibge"]:
            changed_attributes[field] = conn.execute(f"""SELECT COUNT(*) FROM (SELECT {field} current_value,
                LAG({field}) OVER (PARTITION BY cnpj ORDER BY observado_desde) old_value FROM lab_m04.dim_posto) a
                WHERE old_value IS NOT NULL AND current_value <> old_value""").fetchone()[0]
        same_day_ambiguities = conn.execute("""SELECT COUNT(*) FROM (SELECT cnpj, data_coleta FROM (
            SELECT DISTINCT cnpj, data_coleta, bandeira_observada, revenda_observada, municipio_ibge, uf
            FROM lab_m04.stage_coleta) a GROUP BY cnpj, data_coleta HAVING COUNT(*) > 1) b""").fetchone()[0]
        weekly = conn.execute("SELECT SUM(coletas), SUM(soma_precos), COUNT(*) FROM lab_m04.preco_semanal").fetchone()
        total = sum(r["preco_venda"] for r in rows)
        if weekly[:2] != (8052, total):
            raise ValueError("Agregacao semanal nao reconciliou")
        errors_sql = (ROOT / "sql/warehouse/04_reconcile.sql").read_text(encoding="utf-8").split(";")[0]
        checks = dict(conn.execute(errors_sql.replace("COUNT_BIG(*)", "COUNT(*)")).fetchall())
        if any(checks.values()):
            raise ValueError("Reconciliacao local falhou: " + str(checks))
        conn.execute("COPY lab_m04.dim_posto TO '" + (out / "real_station_history.parquet").as_posix().replace("'", "''") + "' (FORMAT PARQUET)")
        conn.execute("COPY (SELECT * FROM lab_m04.preco_semanal ORDER BY inicio_semana_iso, municipio_ibge) TO '" + (out / "real_weekly.parquet").as_posix().replace("'", "''") + "' (FORMAT PARQUET)")
    finally:
        conn.close()
    # Seeds são insumos do laboratório futuro; a geração não executa SQL no Fabric.
    dates = calendar(date(2026, 1, 1), date(2026, 6, 30))
    seed = "-- PREPARADO; executar uma vez no laboratorio vazio, antes das cargas.\n"
    seed += insert("dim_data", dates, list(dates[0])) + "\n"
    seed += insert("dim_municipio", municipalities, ["municipio_ibge", "nome", "uf"]) + "\n"
    (out / "05_seed_reference.sql").write_text(seed, encoding="utf-8")
    base = typed_fixture()
    late = deepcopy(base[1])
    late.update(data_coleta=date(2026, 1, 8), bandeira_observada="LAB C")
    corrected = deepcopy(base)
    for row in corrected[2:]:
        row.update(bandeira_observada=base[0]["bandeira_observada"], revenda_observada=base[0]["revenda_observada"])
    price = deepcopy(base)
    price[0]["preco_venda"] = Decimal("7.000")
    conflict = deepcopy(base[0])
    conflict["bandeira_observada"] = "LAB CONFLITO"
    fixtures = {"10_base": base, "11_late_attribute": base + [late],
                "12_corrected_attribute": corrected, "13_price_only": price,
                "14_rejected_conflict": base + [conflict]}
    for name, values in fixtures.items():
        payload = (json.dumps(values, ensure_ascii=False, default=str, sort_keys=True) + "\n").encode()
        (out / (name + ".json")).write_bytes(payload)
        control = {"batch_id": "lab-m04-" + name, "scope_id": "lab_m04_2026_1_rj_gasolina",
                   "source_sha256": hashlib.sha256(payload).hexdigest(), "ibge_sha256": proof["ibge_sha256"],
                   "silver_delta_version": 0, "is_synthetic": True, "expected_rows": len(values),
                   "expected_stations": 1, "expected_municipalities": 1, "expected_unusual": 0}
        sql = "-- DADOS SINTETICOS. source_sha256 identifica o JSON adjacente; delta_version=0 e um marcador do fixture.\n"
        sql += "BEGIN TRANSACTION;\nDELETE FROM lab_m04.stage_coleta;\nDELETE FROM lab_m04.stage_manifest;\n"
        sql += insert("stage_coleta", values, BUSINESS_FIELDS) + "\n"
        sql += insert("stage_manifest", [control], list(control)) + "\nCOMMIT TRANSACTION;\n"
        sql += "EXEC lab_m04.publish_gold @batch_id = '" + control["batch_id"] + "';\n"
        (out / (name + ".sql")).write_text(sql, encoding="utf-8")
    report = {"run_id": run_id, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "gold_prepared_and_relational_core_validated_locally", "environment": "local_duckdb_not_fabric",
              "duckdb_version": duckdb.__version__, "source_sha256": proof["source_sha256"], "ibge_sha256": proof["ibge_sha256"],
              "input": "M02 pinned reference.parquet, verified by approved manifest SHA", "business_columns_compared": BUSINESS_FIELDS,
              "max_text_bytes_utf8": max_bytes, "stage_text_limits_bytes": widths,
              "counts": {"observations": metrics[0], "stations": metrics[1], "municipalities": metrics[2], "unusual_prices": metrics[3],
                         "station_versions": len(history), "stations_with_multiple_flags": multiple_flags,
                         "stations_with_multiple_versions": multi_version_stations, "observed_attribute_transitions": changed_attributes,
                         "same_day_attribute_ambiguities": same_day_ambiguities, "weekly_groups": weekly[2]},
              "reconciliation_errors": checks, "price_sum_fact": str(total), "price_sum_weekly": str(weekly[1]),
              "same_state_on_replay": before == after, "state_sha256": after,
              "artifacts": out.relative_to(ROOT).as_posix(), "synthetic_inputs_generated": list(fixtures),
              "prepared_sql_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted((ROOT / "sql/warehouse").glob("*.sql"))},
              "generated_input_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in sorted(out.glob("*.sql"))},
              "fabric_executed": False, "tsql_procedure_executed": False,
              "local_adaptations": ["bit -> BOOLEAN; datetime2(6) -> TIMESTAMP in local DDL", "COUNT_BIG(*) -> COUNT(*)", "DATALENGTH UTF8 macro", "CAST(text AS varbinary(8000)) -> encode(text)"],
              "limits": ["DuckDB does not validate Fabric T-SQL compilation, collation or transaction behavior.",
                         "Real history reflects observed snapshots, not legal changes or bitemporal history.",
                         "Official input adapter depends on the accepted M03 publication contract."]}
    evidence = ROOT / "evidence/m04"
    evidence.mkdir(parents=True, exist_ok=True)
    write_json(evidence / "local-gold.json", report)
    print(json.dumps({"status": report["status"], "counts": report["counts"], "checks": checks,
                      "same_state_on_replay": before == after, "artifacts": report["artifacts"], "fabric_executed": False}))


if __name__ == "__main__":
    main()
