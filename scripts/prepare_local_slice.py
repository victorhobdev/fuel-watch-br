"""Ensaio tipado em Parquet; não cria Bronze/Silver Delta nem publica Gold."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from statistics import quantiles
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

from fuelwatch.contract import classify_rows, municipality_lookup
from fuelwatch.source import ROOT, read_anp, read_ibge, source_record

SCHEMA = pa.schema([
    ("cnpj", pa.string()), ("cnpj_origem", pa.string()), ("produto", pa.string()),
    ("data_coleta", pa.date32()), ("preco_venda", pa.decimal128(10, 3)),
    ("moeda", pa.string()), ("unidade", pa.string()), ("uf", pa.string()),
    ("municipio_ibge", pa.string()), ("municipio_origem", pa.string()),
    ("revenda_observada", pa.string()), ("bandeira_observada", pa.string()),
    ("source_record", pa.int64()), ("raw_json", pa.string()),
    ("preco_incomum_iqr", pa.bool_()), ("source_sha256", pa.string()),
    ("ibge_sha256", pa.string()), ("run_id", pa.string()), ("ingested_at_utc", pa.string()),
])


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def prepare():
    scope = json.loads((ROOT / "config/slice.json").read_text(encoding="utf-8"))
    anp, payload = source_record(scope["anp_source_id"])
    ibge, reference = source_record(scope["ibge_source_id"])
    frame, details = read_anp(payload)
    lookup = municipality_lookup(read_ibge(reference, ibge.get("content_encoding")))
    selected = frame[(frame["Estado - Sigla"] == scope["uf"]) & (frame["Produto"] == scope["produto"])]
    rows = [(int(i) + 2, row.to_dict()) for i, row in selected.iterrows()]
    accepted, invalid, duplicates, conflicts = classify_rows(rows, lookup, scope)
    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc).isoformat()
    out = ROOT / "data/local" / scope["scope_id"] / run_id
    out.mkdir(parents=True)
    write_json(out / "quarantine.json", invalid)
    write_json(out / "exact_duplicates.json", duplicates)
    write_json(out / "conflicts.json", conflicts)
    counts = {"received_full_file": len(frame), "outside_slice": len(frame) - len(rows),
              "selected": len(rows), "invalid": len(invalid), "exact_duplicate_excess": len(duplicates),
              "conflicting_rows_after_exact_dedup": len(conflicts), "accepted": len(accepted)}
    assert counts["selected"] == sum(counts[k] for k in ["invalid", "exact_duplicate_excess", "conflicting_rows_after_exact_dedup", "accepted"])
    audit = {"run_id": run_id, "started_at_utc": started, "environment": "local_not_fabric",
             "scope": scope, "source_sha256": anp["sha256"], "ibge_sha256": ibge["sha256"],
             **details, "counts": counts, "status": "blocked_conflict" if conflicts else "validating"}
    write_json(out / "audit.json", audit)
    if conflicts:
        raise ValueError(f"Conflitos de chave; consulta anterior preservada. Auditoria: {out.name}")
    if not accepted:
        raise ValueError("Nenhuma observação válida; consulta anterior preservada")
    # Sinal analítico, não regra de rejeição; calculado só no mesmo produto/UF/unidade/semestre.
    q1, _, q3 = quantiles(sorted(r["preco_venda"] for r in accepted), n=4, method="inclusive") if len(accepted) > 1 else [accepted[0]["preco_venda"]] * 3
    low, high = q1 - Decimal("1.5") * (q3 - q1), q3 + Decimal("1.5") * (q3 - q1)
    business = []
    for row in sorted(accepted, key=lambda r: (r["cnpj"], r["produto"], r["data_coleta"], r["unidade"])):
        row["preco_incomum_iqr"] = not low <= row["preco_venda"] <= high
        business.append({k: row[k] for k in ["cnpj", "produto", "data_coleta", "unidade", "preco_venda", "uf", "municipio_ibge", "revenda_observada", "bandeira_observada"]})
        row.update({"source_sha256": anp["sha256"], "ibge_sha256": ibge["sha256"], "run_id": run_id, "ingested_at_utc": started})
    business_hash = hashlib.sha256(json.dumps(business, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()
    try:
        pq.write_table(pa.Table.from_pylist(accepted, schema=SCHEMA), out / "observacoes.parquet")
        reread = pq.read_table(out / "observacoes.parquet")
        assert reread.num_rows == len(accepted) and reread.schema == SCHEMA
    except Exception as exc:
        audit.update({"status": "failed_local_write", "error_type": type(exc).__name__,
                      "finished_at_utc": datetime.now(timezone.utc).isoformat()})
        write_json(out / "audit.json", audit)
        raise
    summary = []
    for code in sorted({r["municipio_ibge"] for r in accepted}):
        group = [r for r in accepted if r["municipio_ibge"] == code]
        prices = [r["preco_venda"] for r in group]
        summary.append({"municipio_ibge": code, "municipio_anp": group[0]["municipio_origem"],
                        "uf": scope["uf"], "produto": scope["produto"], "moeda": "BRL", "unidade": "litro",
                        "scope_start": scope["date_start"], "scope_end": scope["date_end"],
                        "observations": len(group), "stations": len({r["cnpj"] for r in group}),
                        "date_start": min(r["data_coleta"] for r in group), "date_end": max(r["data_coleta"] for r in group),
                        "min": min(prices), "max": max(prices), "mean_observed_prices": sum(prices) / len(prices)})
    write_json(out / "consumption_by_municipality.json", summary)
    audit.update({"status": "validated_local", "business_sha256": business_hash, "unusual_iqr_rows": sum(r["preco_incomum_iqr"] for r in accepted),
                  "iqr_lower": str(low), "iqr_upper": str(high), "finished_at_utc": datetime.now(timezone.utc).isoformat()})
    write_json(out / "audit.json", audit)
    pointer = ROOT / "data/local" / scope["scope_id"] / "current.json"
    previous = json.loads(pointer.read_text(encoding="utf-8")) if pointer.exists() else None
    # Avança somente após os artefatos e as contagens estarem validados. Execução serial.
    pending = pointer.with_suffix(".pending.json")
    write_json(pending, {"run_id": run_id, "path": out.relative_to(ROOT).as_posix(), "business_sha256": business_hash})
    pending.replace(pointer)
    proof = {**audit, "previous_business_sha256": previous["business_sha256"] if previous else None,
             "same_business_state_as_previous": previous["business_sha256"] == business_hash if previous else None,
             "artifacts": out.relative_to(ROOT).as_posix(), "municipality_count": len(summary)}
    write_json(ROOT / "evidence/local-slice.json", proof)
    print(json.dumps({"run_id": run_id, "counts": counts, "business_sha256": business_hash,
                      "same_business_state_as_previous": proof["same_business_state_as_previous"]}, ensure_ascii=False))
    return proof


if __name__ == "__main__":
    prepare()
