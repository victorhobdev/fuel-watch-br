"""Export privacy-safe, week-addressable station map shards from the checked-in ANP location snapshot.

Run from the workspace root: python web/fuelwatch-atlas/scripts/export_station_map.py
Requires the project's pandas and pyarrow environment.
"""
import gzip
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
OUT = PROJECT / "public" / "data"
LOCATION_FILE = PROJECT / "scripts" / "data" / "anp-station-geography-2026-11-15.json"
PRICE_FILE = ROOT / "data" / "artifacts" / "analytics-history" / "posto_semana.parquet"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"[^a-z0-9]", "", value.encode("ascii", "ignore").decode("ascii").lower())


def main():
    locations = read_json(LOCATION_FILE)
    assert locations["publishedStations"] == len(locations["stations"]) == 8933
    location_by_cnpj = {row["cnpj"]: row for row in locations["stations"]}
    assert len(location_by_cnpj) == len(locations["stations"])

    manifest_path = OUT / "manifest.json"
    manifest = read_json(manifest_path)
    week_indexes = {week: index for index, week in enumerate(manifest["weeks"])}
    prices = pq.read_table(PRICE_FILE, columns=[
        "cnpj", "produto", "inicio_semana_iso", "uf", "municipio_ibge", "municipio_ibge_nome",
        "bandeira_observada", "preco_mediano", "coletas",
    ]).to_pandas()
    assert len(prices) == 2125498
    assert prices["cnpj"].nunique() == 13030
    latest_city = prices.sort_values("inicio_semana_iso").groupby("cnpj", as_index=False).tail(1).set_index("cnpj")
    for cnpj, location in location_by_cnpj.items():
        assert cnpj in latest_city.index
        assert location["uf"] == latest_city.loc[cnpj, "uf"]
        assert normalize(location["municipality"]) == normalize(latest_city.loc[cnpj, "municipio_ibge_nome"])

    prices = prices[prices["cnpj"].isin(location_by_cnpj)].copy()
    prices = prices.sort_values(["produto", "uf", "cnpj", "inicio_semana_iso"])
    assert len(prices) == 1512458
    assert not prices.duplicated(["cnpj", "produto", "inicio_semana_iso"]).any()

    product_files = {}
    for product in manifest["products"]:
        slug = product["id"]
        product_rows = prices[prices["produto"] == product["source"]]
        file_pattern = f"stations/{slug}/{{uf}}.geojson"
        product["stationFile"] = file_pattern
        for state in manifest["states"]:
            state_rows = product_rows[product_rows["uf"] == state["uf"]]
            by_station = defaultdict(list)
            for row in state_rows.itertuples(index=False):
                price_mills = int((Decimal(str(row.preco_mediano)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
                week = week_indexes[str(row.inicio_semana_iso)[:10]]
                by_station[row.cnpj].append([week, price_mills, int(row.coletas)])
            features = []
            for cnpj, weekly_prices in sorted(by_station.items()):
                location = location_by_cnpj[cnpj]
                features.append({
                    "type": "Feature",
                    "properties": {
                        "name": location["name"], "distributor": location["distributor"],
                        "address": location["address"], "complement": location["complement"],
                        "neighborhood": location["neighborhood"], "cep": location["cep"],
                        "municipality": location["municipality"], "municipalityId": str(latest_city.loc[cnpj, "municipio_ibge"]), "uf": location["uf"],
                        "accuracyMeters": location["accuracyMeters"], "origin": location["origin"],
                        "dataObtained": location["dataObtained"], "prices": weekly_prices,
                    },
                    "geometry": {"type": "Point", "coordinates": [location["lon"], location["lat"]]},
                })
            path = OUT / file_pattern.replace("{uf}", state["uf"])
            write_json(path, {"type": "FeatureCollection", "features": features})
            product_files[f"{slug}/{state['uf']}"] = {
                "stations": len(features), "stationWeeks": len(state_rows), "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        print("Exported station weeks", slug, int(product_rows.shape[0]), flush=True)

    manifest["stationLayer"] = {
        "snapshotAt": locations["snapshotAt"], "filePattern": "stations/{product}/{uf}.geojson",
        "stationCount": locations["publishedStations"], "currentCnpjMatches": locations["currentCnpjMatches"],
        "historicalStationCount": locations["historicalStations"], "stationWeekRows": len(prices),
        "stationWeekCoveragePercent": round(len(prices) / 2125498 * 100, 2),
        "accuracyMeters": locations["accuracyMeters"], "validationStatus": locations["validationStatus"],
        "source": locations["source"], "documentation": locations["documentation"],
        "temporalNote": "Coordinates and addresses come from the current ANP registry snapshot; prices remain tied to the selected historical week.",
        "coverageNote": "Only stations with positive ANP-reported accuracy and a municipality matching their latest historical price record are mapped.",
        "files": product_files,
    }
    notes = manifest["dataset"]["notes"]
    note = "Individual station markers use the current ANP registry snapshot from 15/11/2026 and appear only after selecting a state; the ANP marks the coordinates as not geographically validated."
    if note not in notes:
        notes.append(note)
    write_json(manifest_path, manifest)

    validation_path = OUT / "validation.json"
    validation = read_json(validation_path)
    public_files = sorted(path for path in OUT.rglob("*") if path.is_file() and path != validation_path)
    validation.update({
        "stationLocationSnapshotAt": locations["snapshotAt"],
        "stationLocationsPublished": locations["publishedStations"],
        "stationWeekRowsWithLocation": len(prices),
        "stationWeekCoveragePercent": round(len(prices) / 2125498 * 100, 2),
        "payloadFiles": len(public_files), "payloadBytes": sum(path.stat().st_size for path in public_files),
        "payloadGzipBytes": sum(len(gzip.compress(path.read_bytes(), mtime=0)) for path in public_files),
    })
    write_json(validation_path, validation)
    print(json.dumps({
        "stations": locations["publishedStations"], "stationWeeks": len(prices),
        "coveragePercent": round(len(prices) / 2125498 * 100, 2),
        "payloadFiles": validation["payloadFiles"], "payloadBytes": validation["payloadBytes"],
        "payloadGzipBytes": validation["payloadGzipBytes"],
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
