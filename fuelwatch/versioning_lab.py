"""Modelo local sintético do contrato M03; não publica tabelas oficiais nem Delta."""

from copy import deepcopy
import csv
import hashlib
import io
import json

from fuelwatch.contract import classify_rows
from fuelwatch.m02_reference import HEADERS, TYPED_FIELDS

KEY = ["cnpj", "produto", "data_coleta", "unidade"]
LOOKUP = {("RJ", "RIO DE JANEIRO"): ["3304557"]}
SCOPE = {"scope_id": "lab_m03_2026_1_rj_gasolina", "uf": "RJ", "produto": "GASOLINA",
         "date_start": "2026-01-01", "date_end": "2026-06-30", "contract_version": "0.1"}


def business_key(row):
    return tuple(row[field] for field in KEY)


def compare(previous, candidate):
    old, new = ({business_key(row): row for row in rows} for rows in [previous, candidate])
    inserted = sorted(new.keys() - old.keys())
    removed = sorted(old.keys() - new.keys())
    updated = sorted(key for key in new.keys() & old.keys() if new[key] != old[key])
    return {"inserted": [list(k) for k in inserted], "removed": [list(k) for k in removed],
            "updated": [list(k) for k in updated],
            "unchanged": sum(new[k] == old[k] for k in new.keys() & old.keys())}


def fixture_row(day, price, station="00.000.000/0000-00"):
    raw = dict.fromkeys(HEADERS, "")
    raw.update({"Regiao - Sigla": "SE", "Estado - Sigla": "RJ", "Municipio": "RIO DE JANEIRO",
                "Revenda": "LAB M03 SINTETICO", "CNPJ da Revenda": station, "Produto": "GASOLINA",
                "Data da Coleta": day, "Valor de Venda": price, "Unidade de Medida": "R$ / litro",
                "Bandeira": "LAB SINTETICA"})
    return raw


def delivery(scope, rows, supersedes, approved_delta, complete=True):
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, HEADERS, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    payload = text.getvalue().encode("utf-8-sig")
    manifest = {"source_id": "lab_anp_synthetic", "is_synthetic": True, "scope": deepcopy(scope),
                "complete_snapshot": complete, "sha256": hashlib.sha256(payload).hexdigest(),
                "supersedes_sha256": supersedes, "approved_delta": approved_delta}
    return manifest, payload


def apply_delivery(state, scope, manifest, payload, run_id):
    """Transição serial em memória: auditoria/catalogação podem crescer; ativo só avança após aceite."""
    if not scope["scope_id"].startswith("lab_m03_"):
        raise ValueError("Este modelo aceita somente escopos sintéticos lab_m03_")
    result = deepcopy(state)
    result.setdefault("active", {})
    result.setdefault("versions", {})
    source_hash = hashlib.sha256(payload).hexdigest()
    previous = result["active"].get(scope["scope_id"])
    audit = {"run_id": run_id, "environment": "local_synthetic_model_not_fabric", "is_synthetic": True,
             "scope_id": scope["scope_id"], "source_sha256": source_hash,
             "previous_active_sha256": previous["source_sha256"] if previous else None,
             "manifest": deepcopy(manifest)}

    def reject(reason):
        audit.update({"status": "rejected", "reason": reason})
        result["versions"].setdefault(scope["scope_id"] + ":" + source_hash, {"sha256": source_hash})
        return result, audit

    if manifest.get("is_synthetic") is not True or manifest.get("source_id") != "lab_anp_synthetic":
        return reject("source_not_synthetic_lab")
    if manifest.get("scope") != scope:
        return reject("scope_mismatch")
    if manifest.get("sha256") != source_hash:
        return reject("hash_mismatch")
    if manifest.get("complete_snapshot") is not True:
        return reject("incomplete_snapshot")
    if previous and previous["source_sha256"] != source_hash and manifest.get("supersedes_sha256") != previous["source_sha256"]:
        return reject("stale_selection")
    if previous is None and manifest.get("supersedes_sha256") is not None:
        return reject("missing_previous_version")
    try:
        reader = csv.reader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";", strict=True)
        if next(reader) != HEADERS:
            return reject("layout_mismatch")
        received = list(reader)
        if any(len(row) != len(HEADERS) for row in received):
            return reject("field_count_mismatch")
    except (UnicodeDecodeError, csv.Error, StopIteration):
        return reject("unreadable_csv")
    raw_rows = [(index + 2, dict(zip(HEADERS, row))) for index, row in enumerate(received)]
    selected = [(index, raw) for index, raw in raw_rows if raw["Estado - Sigla"] == scope["uf"] and raw["Produto"] == scope["produto"]]
    accepted, invalid, duplicates, conflicts = classify_rows(selected, LOOKUP, scope)
    audit["counts"] = {"received": len(received), "outside_scope": len(received) - len(selected),
                       "selected": len(selected), "accepted": len(accepted), "invalid": len(invalid),
                       "exact_duplicate_excess": len(duplicates), "conflicting_rows": len(conflicts)}
    audit["quarantine"] = invalid
    audit["conflicts"] = conflicts
    if len(selected) != len(accepted) + len(invalid) + len(duplicates) + len(conflicts):
        raise ValueError("Categorias não reconciliam")
    if invalid or conflicts or not accepted:
        return reject("invalid_or_conflicting_or_empty_candidate")
    # Somente os 12 campos tipados de origem; IQR derivado será recalculado na Silver real.
    business = [{k: row[k] for k in TYPED_FIELDS} for row in accepted]
    business = json.loads(json.dumps(sorted(business, key=business_key), default=str, ensure_ascii=False))
    fingerprint = hashlib.sha256(json.dumps(business, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    delta = compare(previous["rows"] if previous else [], business)
    audit.update({"delta": delta, "business_sha256": fingerprint})
    if previous and previous["source_sha256"] == source_hash:
        if previous["business_sha256"] != fingerprint:
            return reject("same_input_different_business_state")
        audit["status"] = "replayed"
        return result, audit
    delta_counts = {k: len(delta[k]) for k in ["inserted", "removed", "updated"]}
    if manifest.get("approved_delta") != delta_counts:
        return reject("change_not_approved")
    result["versions"][scope["scope_id"] + ":" + source_hash] = deepcopy(manifest)
    result["active"][scope["scope_id"]] = {"source_sha256": source_hash, "business_sha256": fingerprint,
                                           "rows": business, "published_run_id": run_id}
    audit["status"] = "published_in_local_model"
    return result, audit


def prepare_cases():
    """Sequência determinística com MAX(data_coleta) constante em junho nas correções aceitas."""
    base = [fixture_row("05/01/2026", "6,10"), fixture_row("12/01/2026", "6,20"),
            fixture_row("02/02/2026", "6,30", "00.000.000/0000-01"), fixture_row("30/06/2026", "6,50")]
    corrected = deepcopy(base)
    corrected[0]["Valor de Venda"] = "6,35"
    late = corrected + [fixture_row("08/01/2026", "6,15", "00.000.000/0000-01")]
    removed = [row for row in late if row["Data da Coleta"] != "12/01/2026"]
    duplicate = removed + [deepcopy(removed[0])]
    return {"base": base, "correction_january": corrected, "late_arrival": late,
            "removed_row": removed, "exact_duplicate": duplicate,
            "conflict": duplicate + [fixture_row("05/01/2026", "8,88")],
            "invalid": duplicate + [fixture_row("10/01/2026", "-1")], "empty": []}
