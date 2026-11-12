"""Transformação PySpark M02: filtro primeiro; contrato Python compartilhado em UDF."""

import json

from pyspark.sql import functions as F, types as T

from fuelwatch.contract import validate_row
from fuelwatch.m02_reference import HEADERS, RAW_COLUMNS, TYPED_FIELDS, BUSINESS_FIELDS, iqr_fences, synthetic_rows

RECORD_SCHEMA = T.StructType([
    T.StructField(name, T.DateType() if name == "data_coleta" else
                  T.DecimalType(10, 3) if name == "preco_venda" else T.StringType(), True)
    for name in TYPED_FIELDS
])
VALIDATION_SCHEMA = T.StructType([
    T.StructField("record", RECORD_SCHEMA, True),
    T.StructField("reasons", T.ArrayType(T.StringType(), False), False),
    T.StructField("raw_json", T.StringType(), False),
])
RAW_SCHEMA = T.StructType([T.StructField(name, T.StringType(), False) for name in RAW_COLUMNS])


def classify(frame, lookup, scope):
    """Retorna categorias e o frame cacheado; o chamador libera o cache ao terminar."""
    def validate(values):
        raw = dict(zip(HEADERS, values))
        record, reasons = validate_row(raw, lookup, scope)
        return {"record": record, "reasons": reasons,
                "raw_json": json.dumps(raw, ensure_ascii=False)}

    validate_udf = F.udf(validate, VALIDATION_SCHEMA, useArrow=False)
    classified = (frame.select(*RAW_COLUMNS)
                  .withColumn("raw_row_sha256", F.sha2(F.to_json(F.struct(*RAW_COLUMNS)), 256))
                  .withColumn("_v", validate_udf(F.array(*[F.col(c) for c in RAW_COLUMNS])))
                  .cache())
    invalid = classified.where(F.size("_v.reasons") > 0).select(
        "raw_row_sha256", F.col("_v.raw_json").alias("raw_json"), F.col("_v.reasons").alias("reasons"))
    valid = classified.where(F.size("_v.reasons") == 0)
    duplicate_groups = valid.groupBy(*RAW_COLUMNS).agg(F.count("*").alias("occurrences")).where("occurrences > 1")
    duplicates = duplicate_groups.select(
        F.sha2(F.to_json(F.struct(*RAW_COLUMNS)), 256).alias("raw_row_sha256"),
        F.to_json(F.struct(*[F.col(c).alias(h) for c, h in zip(RAW_COLUMNS, HEADERS)])).alias("raw_json"),
        "occurrences", (F.col("occurrences") - 1).alias("duplicate_excess"))
    unique = valid.dropDuplicates(RAW_COLUMNS)
    keys = ["cnpj", "produto", "data_coleta", "unidade"]
    for name in keys:
        unique = unique.withColumn("k_" + name, F.col("_v.record." + name))
    key_columns = ["k_" + name for name in keys]
    conflicting_keys = unique.groupBy(*key_columns).count().where("count > 1").select(*key_columns)

    def project(df):
        return df.select(*[F.col("_v.record." + name).alias(name) for name in TYPED_FIELDS],
                         "raw_row_sha256", F.col("_v.raw_json").alias("raw_json"))

    accepted = project(unique.join(conflicting_keys, key_columns, "left_anti"))
    conflicts = project(unique.join(conflicting_keys, key_columns, "inner"))
    return {"classified": classified, "accepted": accepted, "invalid": invalid,
            "duplicates": duplicates, "conflicts": conflicts}


def category_counts(parts):
    counts = {"selected": parts["classified"].count(), "invalid": parts["invalid"].count(),
              "exact_duplicate_excess": int(parts["duplicates"].agg(F.sum("duplicate_excess")).first()[0] or 0),
              "conflicting_rows_after_exact_dedup": parts["conflicts"].count(),
              "accepted": parts["accepted"].count()}
    if counts["selected"] != sum(counts[k] for k in counts if k != "selected"):
        raise ValueError("Categorias de reconciliação não fecham")
    return counts


def flag_unusual(accepted):
    # Coleta limitada a esta fatia didática (8.052 preços), sem arredondamento float.
    prices = [r[0] for r in accepted.select("preco_venda").collect()]
    low, high = iqr_fences(prices)
    return accepted.withColumn("preco_incomum_iqr", ~F.col("preco_venda").between(F.lit(low), F.lit(high))), low, high


def compare_business(left, right):
    a, b = left.select(*BUSINESS_FIELDS), right.select(*BUSINESS_FIELDS)
    if [(f.name, f.dataType) for f in a.schema] != [(f.name, f.dataType) for f in b.schema]:
        raise ValueError("Tipos de negócio diferentes da referência")
    missing = a.exceptAll(b).limit(1).count() > 0
    extra = b.exceptAll(a).limit(1).count() > 0
    if missing or extra:
        raise ValueError(f"Diferenças de negócio: missing={missing}, extra={extra}")
    return {"missing_business_rows": False, "extra_business_rows": False,
            "business_columns_compared": BUSINESS_FIELDS}


def run_fixture(spark, lookup, scope):
    parts = classify(spark.createDataFrame(synthetic_rows(), RAW_SCHEMA), lookup, scope)
    try:
        counts = category_counts(parts)
        expected = {"selected": 14, "invalid": 2, "exact_duplicate_excess": 1,
                    "conflicting_rows_after_exact_dedup": 2, "accepted": 9}
        if counts != expected:
            raise ValueError(f"Fixture Spark divergiu: {counts}")
        accepted, _, _ = flag_unusual(parts["accepted"])
        unusual = accepted.where("preco_incomum_iqr").count()
        if unusual != 1 or accepted.where("preco_venda = 99.900").count() != 1:
            raise ValueError("Preço extremo válido foi rejeitado ou sinalizado incorretamente")
        quarantine = parts["invalid"].withColumn("is_synthetic", F.lit(True))
        quarantine.write.format("delta").mode("overwrite").saveAsTable("lab_m02_quarantine")
        if spark.table("lab_m02_quarantine").where("size(reasons) > 0 AND raw_json IS NOT NULL AND is_synthetic").count() != 2:
            raise ValueError("Quarentena sintética não ficou rastreável")
        return {"status": "fixture_validated", "counts": counts, "unusual_accepted": unusual,
                "quarantine_table": "lab_m02_quarantine", "is_synthetic": True}
    finally:
        parts["classified"].unpersist()
