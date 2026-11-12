from datetime import datetime, timezone
import uuid
from pyspark.sql import functions as F, types as T
from fuelwatch.m02_reference import decode_reference

run_id = str(uuid.uuid4())
audit_dir = files_root / "audit/ibge"
audit_dir.mkdir(parents=True, exist_ok=True)
audit = {"run_id": run_id, "status": "started", "environment": "fabric",
         "source_mode": "preserved_official_http_snapshot_uploaded",
         "source_url": manifest["ibge"]["url"], "ibge_sha256": manifest["ibge"]["sha256"],
         "source_retrieved_at_utc": manifest["ibge"]["retrieved_at_utc"],
         "spark_version": spark.version, "python_version": sys.version.split()[0],
         "started_at_utc": datetime.now(timezone.utc).isoformat(),
         "manifest_sha256": p_expected_manifest_sha256}
try:
    payload = (bundle_dir / "municipios-rj.http.gz").read_bytes()
    rows, lookup = decode_reference(payload, manifest["ibge"]["sha256"])
    if len(rows) != 92:
        raise ValueError("Snapshot IBGE aprovado deve conter 92 municípios")
    raw_path = files_root / "raw/ibge_municipios_rj" / audit["ibge_sha256"] / "municipios-rj.http.gz"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest() != audit["ibge_sha256"]:
        raise ValueError("Snapshot IBGE preservado foi alterado")
    if not raw_path.exists():
        raw_path.write_bytes(payload)
    audit["raw_relative_path"] = raw_path.relative_to(files_root).as_posix()
    schema = T.StructType([T.StructField(c, T.StringType(), False) for c in
                           ["municipio_ibge", "nome", "uf", "nome_normalizado"]])
    reference = spark.createDataFrame(rows, schema)
    reference = (reference.withColumn("ibge_sha256", F.lit(audit["ibge_sha256"]))
                 .withColumn("run_id", F.lit(run_id))
                 .withColumn("retrieved_at_utc", F.lit(audit["source_retrieved_at_utc"]))
                 .withColumn("ingested_at_utc", F.lit(audit["started_at_utc"])))
    (reference.write.format("delta").mode("overwrite")
     .option("replaceWhere", f"ibge_sha256 = '{audit['ibge_sha256']}'")
     .saveAsTable("ref_municipio_ibge"))
    persisted = spark.table("ref_municipio_ibge").where(F.col("ibge_sha256") == audit["ibge_sha256"])
    fields = ["municipio_ibge", "nome", "uf", "nome_normalizado"]
    if persisted.count() != 92 or persisted.select("municipio_ibge").distinct().count() != 92:
        raise ValueError("Contagem/unicidade IBGE não reconciliou")
    if persisted.select(*fields).exceptAll(reference.select(*fields)).limit(1).count() or reference.select(*fields).exceptAll(persisted.select(*fields)).limit(1).count():
        raise ValueError("Referência persistida difere do snapshot")
    audit.update({"status": "ibge_reference_validated", "municipalities": 92,
                  "ambiguous_normalized_keys": 0, "reference_table": "ref_municipio_ibge"})
except Exception as exc:
    audit.update({"status": "failed", "error_type": type(exc).__name__})
    raise
finally:
    audit["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (audit_dir / f"{run_id}.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False))
