"""Perfil completo da entrega; não confundir com validação nacional de todas as regras."""

from datetime import datetime, timezone
from decimal import Decimal
import json
import platform

import pandas as pd
import pyarrow as pa

from fuelwatch.contract import municipality_lookup, normalize_name
from fuelwatch.source import ROOT, read_anp, read_ibge, source_record


def profile():
    scope = json.loads((ROOT / "config/slice.json").read_text(encoding="utf-8"))
    anp, payload = source_record(scope["anp_source_id"])
    ibge, reference = source_record(scope["ibge_source_id"])
    frame, details = read_anp(payload)
    places = read_ibge(reference, ibge.get("content_encoding"))
    lookup = municipality_lookup(places)
    selected = frame[(frame["Estado - Sigla"] == scope["uf"]) & (frame["Produto"] == scope["produto"])].copy()
    dates = pd.to_datetime(frame["Data da Coleta"], format="%d/%m/%Y", errors="coerce")
    canonical = frame.copy()
    for field in ["CNPJ da Revenda", "Produto", "Data da Coleta", "Unidade de Medida"]:
        canonical[field] = canonical[field].str.strip()
    candidate_keys = []
    base = ["CNPJ da Revenda", "Produto", "Data da Coleta"]
    for key in [base, base + ["Unidade de Medida"]]:
        unique = canonical.drop_duplicates()
        conflicting = unique[unique.duplicated(key, keep=False)]
        candidate_keys.append({"columns": key, "duplicate_excess_rows": int(canonical.duplicated(key).sum()),
                               "conflicting_keys_after_exact_dedup": len(conflicting[key].drop_duplicates()),
                               "conflicting_rows_after_exact_dedup": len(conflicting)})
    prices = {}
    for product, group in frame.groupby("Produto"):
        raw_prices = group["Valor de Venda"]
        parseable = raw_prices.str.fullmatch(r"[0-9]{1,7}(,[0-9]{1,3})?")
        values = [Decimal(x.replace(",", ".")) for x in raw_prices[parseable].unique()]
        prices[product] = {"rows": len(group), "min": str(min(values)) if values else None,
                           "max": str(max(values)) if values else None,
                           "invalid_format_or_precision_rows": int((~parseable).sum()),
                           "non_positive_rows": int(sum(Decimal(x.replace(",", ".")) <= 0 for x in raw_prices[parseable])),
                           "max_observed_decimal_scale": int(raw_prices[parseable].str.split(",").map(lambda parts: len(parts[1]) if len(parts) > 1 else 0).max()) if values else None,
                           "units": sorted(group["Unidade de Medida"].unique().tolist())}
    coverage = []
    for name, group in selected.groupby("Municipio"):
        matches = lookup.get((scope["uf"], normalize_name(name)), [])
        coverage.append({"municipio_anp": name, "ibge_matches": matches,
                         "rows": len(group), "stations": group["CNPJ da Revenda"].str.strip().nunique()})
    attributes = selected.groupby("CNPJ da Revenda")[["Revenda", "Bandeira"]].nunique()
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "execution_environment": "local_python_not_fabric",
        "versions": {"python": platform.python_version(), "pandas": pd.__version__, "pyarrow": pa.__version__},
        "sources": {"anp": anp, "ibge": ibge},
        "layout": {**details, "encoding": "utf-8-sig (strict)", "delimiter": ";", "decimal_separator": ",",
                   "columns": [{"name": c, "raw_type": "string", "empty_rows": int(frame[c].eq("").sum()),
                                "distinct_values": int(frame[c].nunique())} for c in frame.columns]},
        "full_file": {"rows": len(frame), "column_count": len(frame.columns),
                      "exact_duplicate_excess_rows": int(frame.duplicated().sum()),
                      "date_start": dates.min().date().isoformat(), "date_end": dates.max().date().isoformat(),
                      "invalid_date_rows": int(dates.isna().sum()), "candidate_keys": candidate_keys,
                      "cnpj_format_invalid_rows": int((~frame["CNPJ da Revenda"].str.strip().str.fullmatch(r"[0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}")).sum()),
                      "cnpj_leading_whitespace_rows": int(frame["CNPJ da Revenda"].str.startswith(" ").sum()),
                      "products": prices},
        "slice": {**scope, "rows": len(selected), "excluded_rows": len(frame) - len(selected),
                  "stations": int(selected["CNPJ da Revenda"].str.strip().nunique()),
                  "municipalities": len(coverage), "exact_duplicate_excess_rows": int(selected.duplicated().sum()),
                  "observed_multiple_station_names": int((attributes["Revenda"] > 1).sum()),
                  "observed_multiple_flags": int((attributes["Bandeira"] > 1).sum()),
                  "municipality_coverage": coverage},
        "ibge": {"municipalities_in_reference": len(places),
                 "ambiguous_normalized_keys": sum(len(ids) > 1 for ids in lookup.values())},
    }
    out = ROOT / "evidence/source-profile.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": out.relative_to(ROOT).as_posix(), "rows": len(frame),
                      "slice_rows": len(selected), "municipalities": len(coverage)}, ensure_ascii=False))
    return result


if __name__ == "__main__":
    profile()
