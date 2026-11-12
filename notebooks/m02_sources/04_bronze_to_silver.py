from datetime import datetime, timezone
import uuid
from pyspark.sql import functions as F
from fuelwatch.m02_reference import decode_reference
from fuelwatch.silver_spark import classify, category_counts, flag_unusual, compare_business, run_fixture

scope = manifest["scope"]
source_sha = manifest["anp"]["sha256"]
ibge_sha = manifest["ibge"]["sha256"]
run_id = str(uuid.uuid4())
audit_dir = files_root / "audit/silver"
audit_dir.mkdir(parents=True, exist_ok=True)
audit = {"run_id": run_id, "status": "started", "environment": "fabric", "scope": scope,
         "source_sha256": source_sha, "ibge_sha256": ibge_sha,
         "manifest_sha256": p_expected_manifest_sha256,
         "spark_version": spark.version, "python_version": sys.version.split()[0],
         "started_at_utc": datetime.now(timezone.utc).isoformat()}
parts = None


def lineage(frame):
    return (frame.withColumn("scope_id", F.lit(scope["scope_id"]))
            .withColumn("source_sha256", F.lit(source_sha)).withColumn("ibge_sha256", F.lit(ibge_sha))
            .withColumn("contract_version", F.lit(scope["contract_version"]))
            .withColumn("run_id", F.lit(run_id)).withColumn("ingested_at_utc", F.lit(audit["started_at_utc"]))
            .withColumn("is_synthetic", F.lit(False)))


try:
    rows, lookup = decode_reference((bundle_dir / "municipios-rj.http.gz").read_bytes(), ibge_sha)
    ref = spark.table("ref_municipio_ibge").where(F.col("ibge_sha256") == ibge_sha)
    expected_ref = spark.createDataFrame(rows, "municipio_ibge string, nome string, uf string, nome_normalizado string")
    ref_fields = expected_ref.columns
    if ref.count() != 92 or ref.select(*ref_fields).exceptAll(expected_ref).limit(1).count() or expected_ref.exceptAll(ref.select(*ref_fields)).limit(1).count():
        raise ValueError("Executar notebook 03: referência IBGE não confere")
    audit["fixture"] = run_fixture(spark, lookup, scope)
    bronze = spark.table("bronze_anp").where(F.col("source_sha256") == source_sha)
    source_rows = bronze.count()
    if source_rows != manifest["anp"]["rows"]:
        raise ValueError("Contagem Bronze da versão aprovada divergiu")
    selected = bronze.where((F.col("uf") == scope["uf"]) & (F.col("produto") == scope["produto"]))
    parts = classify(selected, lookup, scope)
    counts = category_counts(parts)
    counts.update({"received_full_file": source_rows, "outside_slice": source_rows - counts["selected"]})
    audit["counts"] = counts
    # Histórico de diagnóstico por tentativa; não é a tabela de negócio.
    for category, table in [("invalid", "quarantine_preco_anp"),
                             ("duplicates", "audit_duplicatas_exatas_anp"),
                             ("conflicts", "audit_conflitos_anp")]:
        lineage(parts[category]).write.format("delta").mode("append").saveAsTable(table)
    if counts["conflicting_rows_after_exact_dedup"]:
        raise ValueError("Chaves conflitantes bloqueiam Silver; resultado anterior preservado")
    if counts != manifest["reference"]["counts"]:
        raise ValueError("Categorias divergem do baseline aprovado; investigar antes de publicar")
    accepted, low, high = flag_unusual(parts["accepted"])
    reference = spark.read.parquet((bundle_dir / "reference.parquet").relative_to(files_root.parent).as_posix())
    audit["local_reference_comparison"] = compare_business(reference, accepted)
    stations = accepted.select("cnpj").distinct().count()
    municipalities = accepted.select("municipio_ibge").distinct().count()
    unusual = accepted.where("preco_incomum_iqr").count()
    if (stations, municipalities, unusual) != (502, 27, 26):
        raise ValueError("Postos, municípios ou sinais IQR divergem da referência")
    if str(low) != manifest["reference"]["iqr_lower"] or str(high) != manifest["reference"]["iqr_upper"]:
        raise ValueError("Limiares IQR diferem do cálculo decimal local")
    if accepted.groupBy("cnpj", "produto", "data_coleta", "unidade").count().where("count > 1").limit(1).count():
        raise ValueError("Chave de negócio duplicada na Silver candidata")
    before = None
    before_version = None
    if spark.catalog.tableExists("silver_preco_coletado"):
        before_version = int(spark.sql("DESCRIBE HISTORY silver_preco_coletado").agg(F.max("version")).first()[0])
        previous = (spark.sql(f"SELECT * FROM silver_preco_coletado VERSION AS OF {before_version}")
                    .where(F.col("scope_id") == scope["scope_id"]))
        if previous.limit(1).count():
            hashes = previous.select("source_sha256", "ibge_sha256").distinct().collect()
            if len(hashes) != 1 or hashes[0][0] != source_sha or hashes[0][1] != ibge_sha:
                raise ValueError("M02 só repete os mesmos snapshots; promoção de outra versão pertence ao M03")
            compare_business(previous, accepted)
            before = previous
    candidate = lineage(accepted)
    # Escreve apenas a fatia já comparada ao baseline; outras fatias permanecem.
    (candidate.write.format("delta").mode("overwrite")
     .option("replaceWhere", f"scope_id = '{scope['scope_id']}'").saveAsTable("silver_preco_coletado"))
    persisted = spark.table("silver_preco_coletado").where(F.col("scope_id") == scope["scope_id"])
    if persisted.count() != 8052:
        raise ValueError("Contagem Silver persistida não reconciliou")
    compare_business(candidate, persisted)
    same_previous = None
    if before is not None:
        compare_business(before, persisted)
        same_previous = True
    audit.update({"status": "silver_validated", "silver_table": "silver_preco_coletado",
                  "silver_rows": 8052, "stations": stations, "municipalities": municipalities,
                  "unusual_iqr_rows": unusual, "iqr_lower": str(low), "iqr_upper": str(high),
                  "previous_delta_version": before_version, "same_business_as_previous": same_previous,
                  "silver_delta_version": int(spark.sql("DESCRIBE HISTORY silver_preco_coletado").agg(F.max("version")).first()[0])})
except Exception as exc:
    audit.update({"status": "failed", "error_type": type(exc).__name__})
    raise
finally:
    if parts is not None:
        parts["classified"].unpersist()
    audit["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    (audit_dir / f"{run_id}.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False))
