"""Seleção serial da origem oficial aprovada; esta célula não altera o baseline M02."""

import csv
from datetime import datetime, timezone
import uuid
import zipfile

from pyspark.sql import functions as F, types as T
from fuelwatch.m02_reference import HEADERS, RAW_COLUMNS, TYPED_FIELDS, BUSINESS_FIELDS, decode_reference
from fuelwatch.silver_spark import classify, category_counts, flag_unusual, compare_business

ACTIVE = "silver_preco_publicado"
VERSIONS = "silver_preco_versionado"
ATTEMPTS = "anp_publication_attempts"
KEY = ["cnpj", "produto", "data_coleta", "unidade"]
scope = manifest["scope"]
policy = p_publication_policy
validate_publication_policy(policy, manifest)
policy_sha = hashlib.sha256(json.dumps(policy, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
run_id = str(uuid.uuid4())
audit_dir = files_root / "audit/m03_official" / run_id
audit_dir.mkdir(parents=True, exist_ok=False)
audit = {"run_id": run_id, "status": "started", "environment": "fabric", "is_synthetic": False,
         "started_at_utc": datetime.now(timezone.utc).isoformat(), "scope": scope,
         "source_sha256": policy["source_sha256"], "ibge_sha256": policy["ibge_sha256"],
         "bundle_manifest_sha256": p_expected_manifest_sha256, "publication_policy_sha256": policy_sha,
         "policy": policy, "spark_version": spark.version, "python_version": sys.version.split()[0],
         "limits": "Serial reviewed snapshot; no cross-table transaction or concurrent publisher guarantee."}
print(json.dumps({"status": "m03_official_started", "run_id": run_id,
                  "audit_relative_path": audit_dir.relative_to(files_root).as_posix()}))
parts = raw = candidate = None
source_versions = {}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def version(table):
    return int(spark.sql(f"DESCRIBE HISTORY {table}").agg(F.max("version")).first()[0])


def at(table, number):
    return spark.sql(f"SELECT * FROM {table} VERSION AS OF {int(number)}")


def same(left, right):
    if [(f.name, f.dataType) for f in left.schema] != [(f.name, f.dataType) for f in right.schema]:
        raise ValueError("Esquemas diferentes")
    if left.exceptAll(right).limit(1).count() or right.exceptAll(left).limit(1).count():
        raise ValueError("Registros diferentes na comparação integral")


def stream_sha(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def verified_csv():
    source_sha = policy["source_sha256"]
    preserved = files_root / "raw" / policy["source_id"] / source_sha / "ca-2026-01.zip"
    extracted = files_root / "extracted" / policy["source_id"] / source_sha / "source.csv"
    with preserved.open("rb") as stream:
        if stream_sha(stream) != source_sha:
            raise ValueError("ZIP preservado diferente do aprovado")
    with zipfile.ZipFile(preserved) as archive:
        members = [m for m in archive.infolist() if not m.is_dir()]
        if len(members) != 1 or not members[0].filename.lower().endswith(".csv"):
            raise ValueError("ZIP oficial deve conter somente um CSV")
        with archive.open(members[0]) as stream:
            if stream_sha(stream) != manifest["anp"]["csv_sha256"]:
                raise ValueError("CSV no ZIP não corresponde ao aprovado")
    with extracted.open("rb") as stream:
        if stream_sha(stream) != manifest["anp"]["csv_sha256"]:
            raise ValueError("CSV extraído diferente dos bytes oficiais")
    with extracted.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter=";", strict=True)
        if next(reader) != HEADERS:
            raise ValueError("Layout oficial mudou")
        count = 0
        for row in reader:
            if len(row) != 16:
                raise ValueError("CSV com quantidade incorreta de campos")
            count += 1
    if count != manifest["anp"]["rows"]:
        raise ValueError("Quantidade no CSV não reconcilia com o perfil aprovado")
    audit["source_files"] = {"zip_relative_path": preserved.relative_to(files_root).as_posix(),
                             "csv_relative_path": extracted.relative_to(files_root).as_posix(),
                             "csv_sha256": manifest["anp"]["csv_sha256"], "source_rows": count,
                             "complete_snapshot_verified_against_reviewed_profile": True}
    return extracted


def write_output(frame, table, replace=False):
    if table not in {ACTIVE, VERSIONS, ATTEMPTS} or (replace and table != ACTIVE):
        raise ValueError("Escrita fora do contrato de publicação")
    writer = frame.write.format("delta")
    if replace:
        writer = writer.mode("overwrite").option("replaceWhere", f"scope_id = '{scope['scope_id']}'")
    else:
        writer = writer.mode("append")
    writer.saveAsTable(table)


def select_version(label):
    attempt_id = str(uuid.uuid4())
    record = {"run_id": run_id, "attempt_id": attempt_id, "label": label, "status": "received",
              "scope_id": scope["scope_id"], "source_sha256": policy["source_sha256"],
              "ibge_sha256": policy["ibge_sha256"], "publication_policy_sha256": policy_sha,
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "is_synthetic": False}
    dump(audit_dir / f"{label}-received.json", record)
    try:
        before_version = version(ACTIVE) if spark.catalog.tableExists(ACTIVE) else None
        all_before = at(ACTIVE, before_version) if before_version is not None else None
        before = all_before.where(F.col("scope_id") == scope["scope_id"]) if all_before is not None else candidate.limit(0)
        identity_fields = IDENTITY_FIELDS + ["snapshot_id", "publication_policy_sha256"]
        metadata = before.select(*identity_fields).distinct().collect() if all_before is not None else []
        if len(metadata) > 1:
            raise ValueError("Mais de uma identidade/snapshot ativo no mesmo escopo")
        if metadata and (not metadata[0]["snapshot_id"] or not metadata[0]["publication_policy_sha256"]):
            raise ValueError("Seleção ativa sem identificação da publicação")
        previous = {k: metadata[0][k] for k in IDENTITY_FIELDS} if metadata else None
        old = before.select(*KEY, F.struct(*[F.col(c) for c in TYPED_FIELDS]).alias("old"))
        new = candidate.select(*KEY, F.struct(*[F.col(c) for c in TYPED_FIELDS]).alias("new"))
        changes = old.join(new, KEY, "full_outer").withColumn("change",
                  F.when(F.col("old").isNull(), "inserted").when(F.col("new").isNull(), "removed")
                  .when(F.col("old").eqNullSafe(F.col("new")), "unchanged").otherwise("updated"))
        counts = {r["change"]: r["count"] for r in changes.groupBy("change").count().collect()}
        delta = {k: counts.get(k, 0) for k in ["inserted", "removed", "updated"]}
        a, b = before.select(*BUSINESS_FIELDS), candidate.select(*BUSINESS_FIELDS)
        business_equal = not (a.exceptAll(b).limit(1).count() or b.exceptAll(a).limit(1).count())
        record.update({"previous_identity": previous, "delta_counts": delta,
                       "before_delta_version": before_version})
        decision = publication_decision(policy, previous, delta, business_equal)
        if decision == "published":
            relative = f"audit/m03_official/{run_id}/{label}-changes"
            changes.where("change <> 'unchanged'").write.mode("errorifexists").json("Files/" + relative)
            record["record_changes_relative_path"] = relative
            materialized = (candidate.withColumn("scope_id", F.lit(scope["scope_id"]))
                            .withColumn("source_id", F.lit(policy["source_id"]))
                            .withColumn("source_sha256", F.lit(policy["source_sha256"]))
                            .withColumn("ibge_sha256", F.lit(policy["ibge_sha256"]))
                            .withColumn("contract_version", F.lit(scope["contract_version"]))
                            .withColumn("snapshot_id", F.lit(attempt_id))
                            .withColumn("publication_policy_sha256", F.lit(policy_sha))
                            .withColumn("run_id", F.lit(run_id)).withColumn("is_synthetic", F.lit(False)))
            write_output(materialized, VERSIONS)
            stored = spark.table(VERSIONS).where(F.col("snapshot_id") == attempt_id)
            same(materialized, stored.select(*materialized.columns))
            record["candidate_snapshot_id"] = attempt_id
            dump(audit_dir / f"{label}-candidate.json", record)
            # Proteção serial; não é um lock ou uma transação entre tabelas.
            if all_before is not None:
                if version(ACTIVE) != before_version:
                    raise ValueError("Outra execução alterou a seleção ativa")
                same(all_before, spark.table(ACTIVE).select(*all_before.columns))
            elif spark.catalog.tableExists(ACTIVE):
                raise ValueError("Outra execução criou a seleção ativa")
            write_output(materialized, ACTIVE, replace=True)
        after_version = version(ACTIVE)
        all_after = at(ACTIVE, after_version)
        selected = all_after.where(F.col("scope_id") == scope["scope_id"])
        compare_business(candidate, selected)
        identities = selected.select(*IDENTITY_FIELDS).distinct().collect()
        if len(identities) != 1 or identities[0].asDict() != policy_identity(policy):
            raise ValueError("Seleção publicada não corresponde à identidade revisada")
        provenance = selected.select("source_id", "is_synthetic").distinct().collect()
        if len(provenance) != 1 or tuple(provenance[0]) != (policy["source_id"], False):
            raise ValueError("Seleção contém fonte incorreta ou dados sintéticos")
        if decision == "replayed":
            if after_version != before_version:
                raise ValueError("Repetição gerou commit na tabela selecionada")
            same(all_before, all_after.select(*all_before.columns))
        if all_before is not None:
            same(all_before.where(F.col("scope_id") != scope["scope_id"]),
                 all_after.where(F.col("scope_id") != scope["scope_id"]).select(*all_before.columns))
        elif all_after.where(F.col("scope_id") != scope["scope_id"]).limit(1).count():
            raise ValueError("Primeira seleção contém escopo inesperado")
        record.update({"status": decision, "after_delta_version": after_version,
                       "rows": selected.count(), "business_verified": True, "other_scopes_unchanged": True,
                       "selected_snapshot_id": selected.select("snapshot_id").distinct().first()[0]})
    except Exception as exc:
        record.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
        raise
    finally:
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        dump(audit_dir / f"{label}.json", record)
        entry = {"run_id": run_id, "attempt_id": attempt_id, "scope_id": scope["scope_id"],
                 "source_sha256": policy["source_sha256"], "status": record["status"],
                 "audit_json": json.dumps(record, ensure_ascii=False, default=str), "is_synthetic": False}
        write_output(spark.createDataFrame([entry], "run_id string, attempt_id string, scope_id string, source_sha256 string, status string, audit_json string, is_synthetic boolean"), ATTEMPTS)
    print(json.dumps({"event": "official_selection_attempt", **record}, ensure_ascii=False))
    return record


try:
    source_versions = {name: version(name) for name in ["bronze_anp", "ref_municipio_ibge", "silver_preco_coletado"]}
    extracted = verified_csv()
    schema = T.StructType([T.StructField(name, T.StringType(), True) for name in HEADERS])
    raw = (spark.read.schema(schema).option("header", True).option("sep", ";").option("encoding", "UTF-8")
           .option("mode", "FAILFAST").option("multiLine", True).option("quote", '"').option("escape", '"')
           .csv(extracted.relative_to(files_root.parent).as_posix()).toDF(*RAW_COLUMNS).fillna("").cache())
    bronze = at("bronze_anp", source_versions["bronze_anp"]).where(F.col("source_sha256") == policy["source_sha256"])
    if raw.count() != manifest["anp"]["rows"] or bronze.count() != manifest["anp"]["rows"]:
        raise ValueError("Volume CSV/Bronze divergiu")
    same(raw.select(*RAW_COLUMNS), bronze.select(*RAW_COLUMNS))
    audit["raw_bronze_full_comparison"] = {"rows": manifest["anp"]["rows"], "missing_or_extra_rows": False}
    rows, lookup = decode_reference((bundle_dir / "municipios-rj.http.gz").read_bytes(), policy["ibge_sha256"])
    expected = spark.createDataFrame(rows, "municipio_ibge string, nome string, uf string, nome_normalizado string")
    reference = at("ref_municipio_ibge", source_versions["ref_municipio_ibge"]).where(F.col("ibge_sha256") == policy["ibge_sha256"])
    same(expected, reference.select(*expected.columns))
    parts = classify(bronze.where((F.col("uf") == scope["uf"]) & (F.col("produto") == scope["produto"])), lookup, scope)
    counts = category_counts(parts)
    counts.update({"received_full_file": manifest["anp"]["rows"], "outside_slice": manifest["anp"]["rows"] - counts["selected"]})
    audit["counts"] = counts
    if counts != manifest["reference"]["counts"]:
        for name in ["invalid", "duplicates", "conflicts"]:
            parts[name].write.mode("errorifexists").json(f"Files/audit/m03_official/{run_id}/{name}")
        raise ValueError("Candidata diferente das categorias revisadas; não promover")
    accepted, low, high = flag_unusual(parts["accepted"])
    candidate = accepted.select(*BUSINESS_FIELDS, "raw_row_sha256", "raw_json").cache()
    compare_business(spark.read.parquet((bundle_dir / "reference.parquet").relative_to(files_root.parent).as_posix()), candidate)
    baseline = at("silver_preco_coletado", source_versions["silver_preco_coletado"]).where(F.col("scope_id") == scope["scope_id"])
    compare_business(baseline, candidate)
    baseline_identities = baseline.select("source_sha256", "ibge_sha256", "is_synthetic").distinct().collect()
    if len(baseline_identities) != 1 or tuple(baseline_identities[0]) != (policy["source_sha256"], policy["ibge_sha256"], False):
        raise ValueError("Identidade do baseline M02 divergiu")
    stations = candidate.select("cnpj").distinct().count()
    municipalities = candidate.select("municipio_ibge").distinct().count()
    unusual = candidate.where("preco_incomum_iqr").count()
    if (candidate.count(), stations, municipalities, unusual) != (8052, 502, 27, 26):
        raise ValueError("Cobertura da candidata oficial divergiu")
    if (str(low), str(high)) != (manifest["reference"]["iqr_lower"], manifest["reference"]["iqr_upper"]):
        raise ValueError("IQR da candidata divergiu")
    if candidate.groupBy(*KEY).count().where("count > 1").limit(1).count():
        raise ValueError("Chave duplicada na candidata")
    audit["registration"] = select_version("registration")
    audit["replay"] = select_version("replay")
    if audit["replay"]["status"] != "replayed" or audit["registration"]["selected_snapshot_id"] != audit["replay"]["selected_snapshot_id"]:
        raise ValueError("Repetição alterou a seleção do snapshot")
    selected_version = audit["replay"]["after_delta_version"]
    audit.update({"status": "m03_official_selection_validated", "official_integration_implemented": True,
                  "silver_rows": 8052, "stations": stations, "municipalities": municipalities,
                  "unusual_iqr_rows": unusual, "replay_without_active_commit": True,
                  "consumer_contract": {"table": ACTIVE, "delta_version": selected_version,
                                        "scope_id": scope["scope_id"], "source_sha256": policy["source_sha256"],
                                        "ibge_sha256": policy["ibge_sha256"], "business_fields": BUSINESS_FIELDS,
                                        "snapshot_id": audit["replay"]["selected_snapshot_id"],
                                        "read_strategy": "Pin Delta version, filter scope, reconcile identity before Gold"},
                  "audit_relative_path": audit_dir.relative_to(files_root).as_posix()})
except Exception as exc:
    audit.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
    raise
finally:
    try:
        unchanged = all(version(table) == number for table, number in source_versions.items()) if source_versions else None
        audit["input_delta_versions"] = source_versions
        audit["m02_inputs_unchanged"] = unchanged
        if unchanged is False:
            audit["status"] = "failed"
            raise ValueError("Uma tabela M02 mudou durante a execução; investigar concorrência")
    finally:
        for frame in [raw, candidate, parts["classified"] if parts else None]:
            if frame is not None:
                frame.unpersist()
        audit["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        dump(audit_dir / "summary.json", audit)
print(json.dumps(audit, ensure_ascii=False))
