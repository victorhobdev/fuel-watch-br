"""Consome o contrato oficial M03 e exporta somente a seleção revisada para Gold."""
from datetime import date, datetime, timedelta, timezone
import uuid

from pyspark.sql import functions as F
from fuelwatch.m02_reference import BUSINESS_FIELDS, decode_reference
from fuelwatch.silver_spark import compare_business

batch_id = str(uuid.uuid4())
audit_root = files_root / "audit/m04" / batch_id
audit_root.mkdir(parents=True, exist_ok=False)
audit = {"batch_id": batch_id, "status": "started", "environment": "fabric",
         "started_at_utc": datetime.now(timezone.utc).isoformat(), "bundle_manifest_sha256": p_expected_manifest_sha256,
         "spark_version": spark.version, "python_version": sys.version.split()[0],
         "source_table": "silver_preco_publicado",
         "source_sha256": manifest["source_sha256"], "ibge_sha256": manifest["ibge_sha256"],
         "is_synthetic": False, "official_republication_promoted": False}
frames = []


def transfer(frame, name):
    table = "m04_transfer_" + name
    output = frame.withColumn("batch_id", F.lit(batch_id))
    output.write.format("delta").mode("append").saveAsTable(table)
    actual = spark.table(table).where(F.col("batch_id") == batch_id)
    if actual.count() != output.count() or actual.exceptAll(output).limit(1).count() or output.exceptAll(actual).limit(1).count():
        raise ValueError("Transferencia nao reconciliou: " + table)
    audit.setdefault("tables", {})[table] = actual.count()


try:
    if not spark.catalog.tableExists("silver_preco_publicado"):
        raise ValueError("Concluir selecao oficial M03 no notebook 06 primeiro")
    current_version = int(spark.sql("DESCRIBE HISTORY silver_preco_publicado").agg(F.max("version")).first()[0])
    current = spark.sql(f"SELECT * FROM silver_preco_publicado VERSION AS OF {current_version}").where(F.col("scope_id") == manifest["scope"]["scope_id"])
    active_ids = current.select("snapshot_id").distinct().collect()
    if len(active_ids) != 1:
        raise ValueError("Selecao ativa sem snapshot unico")
    summaries = []
    for path in sorted((files_root / "audit/m03_official").glob("*/summary.json")):
        try:
            summaries.append((path.relative_to(files_root).as_posix(), json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError:
            audit.setdefault("incomplete_m03_audit_files", []).append(path.relative_to(files_root).as_posix())
    summary_path, contract = select_m03_contract(summaries, manifest, active_ids[0][0])
    source_version = contract["delta_version"]
    audit.update({"source_delta_version": source_version, "snapshot_id": contract["snapshot_id"],
                  "consumer_contract": contract, "m03_summary_relative_path": summary_path})
    source = (spark.sql(f"SELECT * FROM silver_preco_publicado VERSION AS OF {source_version}")
              .where(F.col("scope_id") == manifest["scope"]["scope_id"]).cache())
    frames.append(source)
    provenance = source.select("source_sha256", "ibge_sha256", "is_synthetic", "source_id").distinct().collect()
    if len(provenance) != 1 or tuple(provenance[0]) != (manifest["source_sha256"], manifest["ibge_sha256"], False, manifest["scope"]["anp_source_id"]):
        raise ValueError("Proveniencia Silver divergiu")
    identities = source.select("snapshot_id", "contract_version").distinct().collect()
    if len(identities) != 1 or tuple(identities[0]) != (contract["snapshot_id"], manifest["scope"]["contract_version"]):
        raise ValueError("Identidade da selecao fixada divergiu do consumer_contract")
    current_metadata = current.select("snapshot_id", "source_sha256", "ibge_sha256", "contract_version", "is_synthetic", "source_id").distinct().collect()
    if len(current_metadata) != 1 or tuple(current_metadata[0]) != (contract["snapshot_id"], manifest["source_sha256"],
            manifest["ibge_sha256"], manifest["scope"]["contract_version"], False, manifest["scope"]["anp_source_id"]):
        raise ValueError("Identidade ativa atual divergiu da selecao oficial revisada")
    def parquet(name):
        return spark.read.parquet((bundle_dir / name).relative_to(files_root.parent).as_posix())
    compare_business(parquet("reference.parquet"), source)
    compare_business(source, current)
    counts = (source.count(), source.select("cnpj").distinct().count(),
              source.select("municipio_ibge").distinct().count(), source.where("preco_incomum_iqr").count())
    if counts != (8052, 502, 27, 26):
        raise ValueError("Cobertura aprovada divergiu")
    rows, _ = decode_reference((bundle_dir / "municipios-rj.http.gz").read_bytes(), manifest["ibge_sha256"])
    municipalities = spark.createDataFrame([(r["municipio_ibge"], r["nome"], r["uf"]) for r in rows],
                                           "municipio_ibge string, nome string, uf string")
    dates = []
    day = date(2026, 1, 1)
    while day <= date(2026, 6, 30):
        iso = day.isocalendar()
        dates.append((int(day.strftime("%Y%m%d")), day, day - timedelta(days=day.weekday()), iso.year, iso.week))
        day += timedelta(days=1)
    calendar = spark.createDataFrame(dates, "data_sk int, data date, inicio_semana_iso date, ano_iso int, semana_iso int")
    transfer(source.select(*BUSINESS_FIELDS), "coletas")
    transfer(municipalities, "municipios")
    transfer(calendar, "calendar")
    transfer(parquet("expected_history.parquet"), "expected_posto")
    weekly_fields = ["inicio_semana_iso", "ano_iso", "semana_iso", "municipio_ibge", "produto", "moeda", "unidade",
                     "coletas", "postos_observados", "soma_precos", "preco_minimo", "preco_maximo", "precos_incomuns"]
    transfer(parquet("expected_weekly.parquet").select(*weekly_fields), "expected_weekly")
    if int(spark.sql("DESCRIBE HISTORY silver_preco_publicado").agg(F.max("version")).first()[0]) != current_version:
        raise ValueError("Silver mudou durante a exportacao; lote nao sera marcado pronto")
    control = spark.createDataFrame([(batch_id, manifest["scope"]["scope_id"], manifest["source_sha256"],
        manifest["ibge_sha256"], source_version, False, 8052, 502, 27, 26, "silver_preco_publicado", contract["snapshot_id"])],
        "batch_id string, scope_id string, source_sha256 string, ibge_sha256 string, silver_delta_version long, "
        "is_synthetic boolean, expected_rows long, expected_stations long, expected_municipalities long, expected_unusual long, source_table string, snapshot_id string")
    # Manifesto pronto é escrito por último; lote incompleto fica sem esta marca.
    control.write.format("delta").mode("append").saveAsTable("m04_transfer_manifest")
    audit.update({"status": "m04_transfer_ready", "coletas": 8052, "stations": 502, "municipalities": 27,
                  "unusual_prices": 26, "silver_unchanged": True,
                  "warehouse_next_file": "30_import_approved_snapshot.sql",
                  "sql_batch_parameter": batch_id})
except Exception as exc:
    audit.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
    raise
finally:
    for frame in frames:
        frame.unpersist()
    audit["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (audit_root / "transfer.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False))
