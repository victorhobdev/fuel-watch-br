"""Célula executada no Fabric: laboratório serial Spark/Delta, sem escrita oficial."""

from datetime import date, datetime, timezone
from decimal import Decimal
import csv
import io
import uuid

from pyspark.sql import functions as F, types as T
from fuelwatch.m02_reference import HEADERS, RAW_COLUMNS, TYPED_FIELDS, BUSINESS_FIELDS
from fuelwatch.silver_spark import RECORD_SCHEMA, RAW_SCHEMA, classify, category_counts, flag_unusual, compare_business

KEY = ["cnpj", "produto", "data_coleta", "unidade"]
ACTIVE = "lab_m03_active"
VERSIONS = "lab_m03_versions"
ATTEMPTS = "lab_m03_attempts"
ALLOWED_TABLES = {ACTIVE, VERSIONS, ATTEMPTS}
PROTECTED = "lab_m03_protected_scope"
BUSINESS_SCHEMA = T.StructType(list(RECORD_SCHEMA.fields) + [T.StructField("preco_incomum_iqr", T.BooleanType(), False)])
ATTEMPT_SCHEMA = "experiment_id string, attempt_id string, scenario string, scope_id string, source_sha256 string, status string, started_at_utc string, finished_at_utc string, audit_json string, is_synthetic boolean"


class InjectedBeforePromotion(RuntimeError):
    """Falha Python controlada; não simula perda do cluster ou falha no commit Delta."""


plan = json.loads((bundle_dir / "scenarios.json").read_text(encoding="utf-8"))
scope = manifest["scope"]
if manifest.get("bundle_version") != "m03-v1" or manifest.get("is_synthetic") is not True:
    raise ValueError("Pacote não é do laboratório M03")
if plan["scope"] != scope or scope["scope_id"] != "lab_m03_2026_1_rj_gasolina" or not plan["is_synthetic"]:
    raise ValueError("Escopo sintético diferente do esperado")
if len(plan["scenarios"]) != manifest["scenario_count"] or manifest["scenario_count"] != 17:
    raise ValueError("Roteiro deve conter exatamente 17 tentativas")
# Fixture de até 20 linhas: limitar as partições de shuffle somente nesta sessão dedicada.
spark.conf.set("spark.sql.shuffle.partitions", "4")
experiment_id = str(uuid.uuid4())
audit_root = files_root / "audit/m03" / experiment_id
landing_root = files_root / "lab_m03/landing" / experiment_id
audit_root.mkdir(parents=True, exist_ok=False)
landing_root.mkdir(parents=True, exist_ok=False)
summary = {"experiment_id": experiment_id, "status": "started", "environment": "fabric",
           "is_synthetic": True, "started_at_utc": datetime.now(timezone.utc).isoformat(),
           "manifest_sha256": p_expected_manifest_sha256, "spark_version": spark.version,
           "python_version": sys.version.split()[0], "scenario_results": [],
           "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
           "tables": sorted(ALLOWED_TABLES), "official_integration_implemented": False,
           "limits": "Serial synthetic lab; no cross-table transaction or concurrent publication guarantee."}
print(json.dumps({"status": "m03_lab_started", "experiment_id": experiment_id,
                  "audit_relative_path": audit_root.relative_to(files_root).as_posix()}))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def table_version(table):
    return int(spark.sql(f"DESCRIBE HISTORY {table}").agg(F.max("version")).first()[0])


def snapshot(table, version):
    return spark.sql(f"SELECT * FROM {table} VERSION AS OF {int(version)}")


def experiment_at(version):
    return snapshot(ACTIVE, version).where(F.col("experiment_id") == experiment_id)


def equal_all(left, right):
    if [(f.name, f.dataType) for f in left.schema] != [(f.name, f.dataType) for f in right.schema]:
        raise ValueError("Esquemas incompatíveis na comparação integral")
    if left.exceptAll(right).limit(1).count() or right.exceptAll(left).limit(1).count():
        raise ValueError("Comparação integral encontrou diferença de registros")


def write_lab(frame, table, predicate=None):
    if table not in ALLOWED_TABLES:
        raise ValueError("Escrita fora das tabelas permitidas")
    writer = frame.write.format("delta").partitionBy("experiment_id")
    if predicate is not None:
        if table != ACTIVE or predicate != active_predicate:
            raise ValueError("Substituição não autorizada")
        writer = writer.mode("overwrite").option("replaceWhere", predicate)
    else:
        writer = writer.mode("append")
    writer.saveAsTable(table)


def expected_frame(rows):
    typed = []
    for item in rows:
        row = dict(item)
        row["data_coleta"] = date.fromisoformat(row["data_coleta"])
        row["preco_venda"] = Decimal(row["preco_venda"])
        typed.append(row)
    return spark.createDataFrame(typed, BUSINESS_SCHEMA)


def lineage(frame, scope_id, source_sha, attempt_id):
    return (frame.select(*BUSINESS_FIELDS).withColumn("experiment_id", F.lit(experiment_id))
            .withColumn("scope_id", F.lit(scope_id)).withColumn("source_sha256", F.lit(source_sha))
            .withColumn("snapshot_id", F.lit(attempt_id)).withColumn("promoted_by_attempt", F.lit(attempt_id))
            .withColumn("is_synthetic", F.lit(True)))


def differences(before, after):
    old = before.select(*KEY, F.struct(*[F.col(c) for c in TYPED_FIELDS]).alias("before"))
    new = after.select(*KEY, F.struct(*[F.col(c) for c in TYPED_FIELDS]).alias("after"))
    joined = old.join(new, KEY, "full_outer")
    result = joined.select(*KEY, "before", "after", F.when(F.col("before").isNull(), "inserted")
                           .when(F.col("after").isNull(), "removed")
                           .when(F.col("before").eqNullSafe(F.col("after")), "unchanged")
                           .otherwise("updated").alias("change"))
    rows = [r.asDict(recursive=True) for r in result.collect()]
    return {k: sum(r["change"] == k for r in rows) for k in ["inserted", "removed", "updated"]}, rows


def preflight(delivery_manifest, payload, previous_sha):
    if delivery_manifest.get("is_synthetic") is not True or delivery_manifest.get("source_id") != "lab_anp_synthetic":
        return "source_not_synthetic_lab", None
    if delivery_manifest.get("scope") != scope:
        return "scope_mismatch", None
    source_sha = hashlib.sha256(payload).hexdigest()
    if delivery_manifest.get("sha256") != source_sha:
        return "hash_mismatch", None
    if delivery_manifest.get("complete_snapshot") is not True:
        return "incomplete_snapshot", None
    if previous_sha and previous_sha != source_sha and delivery_manifest.get("supersedes_sha256") != previous_sha:
        return "stale_selection", None
    if not previous_sha and delivery_manifest.get("supersedes_sha256") is not None:
        return "missing_previous_version", None
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";", strict=True)
        if next(reader) != HEADERS:
            return "layout_mismatch", None
        rows = list(reader)
        if len(rows) > 20:
            raise ValueError("Este laboratório aceita somente fixtures pequenas")
        if any(len(row) != len(HEADERS) for row in rows):
            return "field_count_mismatch", None
    except (UnicodeDecodeError, csv.Error, StopIteration):
        return "unreadable_csv", None
    return None, [dict(zip(RAW_COLUMNS, row)) for row in rows]


def run_scenario(step, ordinal):
    attempt_id = str(uuid.uuid4())
    folder = audit_root / f"{ordinal:02d}_{step['name']}"
    folder.mkdir()
    landing = landing_root / attempt_id
    landing.mkdir()
    payload = step["csv_utf8"].encode("utf-8")
    source_sha = hashlib.sha256(payload).hexdigest()
    (landing / "source.csv").write_bytes(payload)
    dump(landing / "manifest.json", step["manifest"])
    before_version = table_version(ACTIVE)
    before_all = experiment_at(before_version)
    before = before_all.where(F.col("scope_id") == scope["scope_id"])
    prior_hashes = before.select("source_sha256").distinct().collect()
    if len(prior_hashes) > 1:
        raise ValueError("Mais de uma versão ativa no mesmo escopo")
    previous_sha = prior_hashes[0][0] if prior_hashes else None
    audit = {"attempt_id": attempt_id, "experiment_id": experiment_id, "scenario": step["name"],
             "scope_id": scope["scope_id"], "source_sha256": source_sha,
             "previous_active_sha256": previous_sha, "before_delta_version": before_version,
             "manifest": step["manifest"], "landing_relative_path": landing.relative_to(files_root).as_posix(),
             "status": "received", "environment": "fabric", "is_synthetic": True,
             "started_at_utc": datetime.now(timezone.utc).isoformat()}
    parts = None
    dump(folder / "received.json", audit)
    dump(folder / "active-before.json", [r.asDict(recursive=True) for r in before_all.collect()])
    try:
        reason, raw = preflight(step["manifest"], payload, previous_sha)
        candidate = None
        if reason is None:
            frame = spark.createDataFrame(raw, RAW_SCHEMA)
            selected = frame.where((F.col("uf") == scope["uf"]) & (F.col("produto") == scope["produto"]))
            parts = classify(selected, {("RJ", "RIO DE JANEIRO"): ["3304557"]}, scope)
            counts = category_counts(parts)
            counts.update({"received": len(raw), "outside_scope": len(raw) - counts["selected"]})
            audit["counts"] = counts
            for key in ["invalid", "duplicates", "conflicts"]:
                audit[key] = [r.asDict(recursive=True) for r in parts[key].collect()]
            if counts["invalid"] or counts["conflicting_rows_after_exact_dedup"] or not counts["accepted"]:
                reason = "invalid_or_conflicting_or_empty_candidate"
            else:
                candidate, low, high = flag_unusual(parts["accepted"])
                candidate = candidate.select(*BUSINESS_FIELDS)
                delta, rows = differences(before, candidate)
                audit.update({"delta_counts": delta, "record_differences": rows,
                              "iqr_lower": str(low), "iqr_upper": str(high)})
                if previous_sha == source_sha:
                    compare_business(before, candidate)
                    audit["status"] = "replayed"
                elif step["manifest"].get("approved_delta") != delta:
                    reason = "change_not_approved"
                else:
                    version = lineage(candidate, scope["scope_id"], source_sha, attempt_id)
                    write_lab(version, VERSIONS)
                    stored = spark.table(VERSIONS).where((F.col("experiment_id") == experiment_id) &
                                                       (F.col("snapshot_id") == attempt_id))
                    equal_all(version, stored.select(*version.columns))
                    audit["candidate_snapshot_id"] = attempt_id
                    audit["status"] = "candidate_materialized"
                    dump(folder / "candidate-materialized.json", audit)
                    try:
                        if step["inject_before_promotion"]:
                            raise InjectedBeforePromotion("Candidata persistida; publicação ainda não iniciada")
                        # Conferir a seleção antes de promover; este ensaio exige execução serial.
                        equal_all(before_all, experiment_at(table_version(ACTIVE)))
                        write_lab(version, ACTIVE, active_predicate)
                        audit["status"] = "published"
                    except InjectedBeforePromotion:
                        reason = "injected_before_promotion"
                        audit["status"] = "failed_before_promotion"
        if reason and audit["status"] != "failed_before_promotion":
            audit["status"] = "rejected"
        audit["reason"] = reason
        after_version = table_version(ACTIVE)
        after_all = experiment_at(after_version)
        after = after_all.where(F.col("scope_id") == scope["scope_id"])
        audit["after_delta_version"] = after_version
        if audit["status"] in ["rejected", "replayed", "failed_before_promotion"]:
            equal_all(before_all, after_all)
            if after_version != before_version:
                raise ValueError("Uma tentativa sem publicação gerou commit na tabela ativa")
        elif after_version <= before_version:
            raise ValueError("Publicação não gerou nova versão Delta")
        equal_all(before_all.where(F.col("scope_id") == PROTECTED), after_all.where(F.col("scope_id") == PROTECTED))
        if audit["status"] != step["expected_status"] or audit["reason"] != step["expected_reason"]:
            raise ValueError(f"Cenário {step['name']} divergiu: {audit['status']} / {audit['reason']}")
        compare_business(expected_frame(step["expected_active_rows"]), after)
        expected_sha = step["expected_active_sha256"]
        actual_hashes = after.select("source_sha256").distinct().collect()
        if [r[0] for r in actual_hashes] != ([expected_sha] if expected_sha else []):
            raise ValueError("A seleção ativa não corresponde ao hash esperado")
        dump(folder / "active-after.json", [r.asDict(recursive=True) for r in after_all.collect()])
        audit["verified"] = {"business_matches_expected": True, "protected_scope_unchanged": True,
                             "active_source_matches_expected": True, "delta_commit_behavior": True}
    except Exception as exc:
        audit.update({"status": "failed_unexpected", "error_type": type(exc).__name__, "error": str(exc)})
        raise
    finally:
        if parts is not None:
            parts["classified"].unpersist()
        audit["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        dump(folder / "audit.json", audit)
        entry = {k: audit[k] for k in ["experiment_id", "attempt_id", "scenario", "scope_id", "source_sha256",
                                      "status", "started_at_utc", "finished_at_utc", "is_synthetic"]}
        entry["audit_json"] = json.dumps(audit, ensure_ascii=False, default=str)
        write_lab(spark.createDataFrame([entry], ATTEMPT_SCHEMA), ATTEMPTS)
    result = {"scenario": step["name"], "status": audit["status"], "reason": audit["reason"],
              "attempt_id": attempt_id, "before_delta_version": before_version,
              "after_delta_version": after_version, "delta_counts": audit.get("delta_counts"),
              "verified": audit["verified"]}
    print(json.dumps({"event": "m03_scenario_verified", **result}, ensure_ascii=False))
    return result


official_before = None
official_version = None
try:
    guard = manifest["official_guard"]
    if guard["table"] != "silver_preco_coletado":
        raise ValueError("Tabela oficial de referência não confere")
    official_version = table_version(guard["table"])
    official_before = snapshot(guard["table"], official_version).cache()
    official_before.count()
    baseline = official_before.where(F.col("scope_id") == guard["scope"]["scope_id"])
    if baseline.count() != guard["rows"] or baseline.select("cnpj").distinct().count() != 502 or baseline.select("municipio_ibge").distinct().count() != 27:
        raise ValueError("Baseline M02 divergiu: não iniciar M03")
    hashes = baseline.select("source_sha256", "ibge_sha256", "is_synthetic").distinct().collect()
    if len(hashes) != 1 or tuple(hashes[0]) != (guard["source_sha256"], guard["ibge_sha256"], False):
        raise ValueError("Snapshots oficiais diferem do baseline M02")
    active_predicate = f"experiment_id = '{experiment_id}' AND scope_id = '{scope['scope_id']}'"
    seed = lineage(expected_frame(plan["scenarios"][0]["expected_active_rows"][:1]), PROTECTED, "0" * 64, "protected_seed")
    write_lab(seed, ACTIVE)
    for ordinal, step in enumerate(plan["scenarios"], 1):
        summary["scenario_results"].append(run_scenario(step, ordinal))
        dump(audit_root / "progress.json", summary)
    final = experiment_at(table_version(ACTIVE)).where(F.col("scope_id") == scope["scope_id"])
    if final.count() != 4 or str(final.agg(F.max("data_coleta")).first()[0]) != "2026-06-30":
        raise ValueError("Estado final do laboratório divergiu")
    recorded = spark.table(ATTEMPTS).where(F.col("experiment_id") == experiment_id)
    if recorded.count() != 17 or recorded.select("attempt_id").distinct().count() != 17:
        raise ValueError("Auditorias persistidas não reconciliam")
    status_counts = {r["status"]: r["count"] for r in recorded.groupBy("status").count().collect()}
    if status_counts != {"published": 7, "replayed": 1, "rejected": 8, "failed_before_promotion": 1}:
        raise ValueError("Estados das tentativas persistidas divergiram")
    versions = spark.table(VERSIONS).where(F.col("experiment_id") == experiment_id)
    if versions.count() != 33 or versions.select("snapshot_id").distinct().count() != 8:
        raise ValueError("Histórico de candidatas não reconciliou, incluindo a tentativa com falha")
    summary.update({"status": "m03_lab_validated", "scenarios_verified": len(summary["scenario_results"]),
                    "final_rows": 4, "final_active_delta_version": table_version(ACTIVE),
                    "attempt_status_counts": status_counts, "candidate_snapshots": 8,
                    "injected_failure_recovered": True, "official_delta_version_before": official_version,
                    "audit_relative_path": audit_root.relative_to(files_root).as_posix()})
except Exception as exc:
    summary.update({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)})
    raise
finally:
    try:
        if official_before is not None:
            after_version = table_version("silver_preco_coletado")
            summary["official_delta_version_after"] = after_version
            equal_all(official_before, snapshot("silver_preco_coletado", after_version))
            if after_version != official_version:
                raise ValueError("Versão Delta oficial mudou durante o laboratório; investigar outra execução")
            summary["official_silver_unchanged"] = True
    except Exception as guard_exc:
        summary.update({"status": "failed", "official_silver_unchanged": False,
                        "official_guard_error": str(guard_exc)})
        raise
    finally:
        if official_before is not None:
            official_before.unpersist()
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        dump(audit_root / "summary.json", summary)
print(json.dumps(summary, ensure_ascii=False))
