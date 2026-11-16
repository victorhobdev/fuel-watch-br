"""Export the approved local analytical snapshot. Never calls Fabric or changes inputs.

Run from any directory: python web/fuelwatch-atlas/scripts/export_snapshot.py
Requires the project's pandas, pyarrow and duckdb. Existing geometry is reused;
--refresh-geography explicitly fetches the official simplified IBGE snapshot.
"""
import argparse
import gzip
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "public" / "data"
ANALYTICS = ROOT / "data/artifacts/analytics-history"
PUBLICATION = ROOT / "data/artifacts/history/publication"
PRODUCTS = [
    ("gasolina", "Gasolina comum", "GASOLINA", "litro"),
    ("gasolina-aditivada", "Gasolina aditivada", "GASOLINA ADITIVADA", "litro"),
    ("etanol", "Etanol", "ETANOL", "litro"),
    ("diesel", "Diesel comum", "DIESEL", "litro"),
    ("diesel-s10", "Diesel S10", "DIESEL S10", "litro"),
    ("gnv", "GNV", "GNV", "m3"),
]
STATE_ROWS = [
    (11,"RO","Rondônia","Norte"),(12,"AC","Acre","Norte"),
    (13,"AM","Amazonas","Norte"),(14,"RR","Roraima","Norte"),
    (15,"PA","Pará","Norte"),(16,"AP","Amapá","Norte"),
    (17,"TO","Tocantins","Norte"),(21,"MA","Maranhão","Nordeste"),
    (22,"PI","Piauí","Nordeste"),(23,"CE","Ceará","Nordeste"),
    (24,"RN","Rio Grande do Norte","Nordeste"),(25,"PB","Paraíba","Nordeste"),
    (26,"PE","Pernambuco","Nordeste"),(27,"AL","Alagoas","Nordeste"),
    (28,"SE","Sergipe","Nordeste"),(29,"BA","Bahia","Nordeste"),
    (31,"MG","Minas Gerais","Sudeste"),(32,"ES","Espírito Santo","Sudeste"),
    (33,"RJ","Rio de Janeiro","Sudeste"),(35,"SP","São Paulo","Sudeste"),
    (41,"PR","Paraná","Sul"),(42,"SC","Santa Catarina","Sul"),
    (43,"RS","Rio Grande do Sul","Sul"),(50,"MS","Mato Grosso do Sul","Centro-Oeste"),
    (51,"MT","Mato Grosso","Centro-Oeste"),(52,"GO","Goiás","Centro-Oeste"),
    (53,"DF","Distrito Federal","Centro-Oeste"),
]
STATES = [dict(id=str(i), uf=u, name=n, region=r) for i,u,n,r in STATE_ROWS]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                               allow_nan=False), encoding="utf-8")


def typed_hash(row, kinds):
    # Exact normalization used by fuelwatch.analytics, without importing/mutating it.
    values = []
    for v, kind in zip(row, kinds):
        if v is None or (kind != "str" and str(v) in {"nan", "NaT", "<NA>"}):
            values.append(None)
        elif kind == "decimal":
            values.append(str(Decimal(str(v)).quantize(Decimal(".000001"), rounding=ROUND_HALF_UP)))
        elif kind == "date":
            values.append(str(v)[:10])
        elif kind in {"int", "bool"}:
            values.append(str(int(v)))
        else:
            values.append(str(v))
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def verify_sources():
    local = read_json(ANALYTICS / "reference.json")
    remote = read_json(ROOT / "evidence/phase2/analytics-history/warehouse-verification.json")
    checks = {}
    for name in ["posto_semana", "referencia_uf_semana", "municipio_semana"]:
        expected = local[name]
        assert remote["tables"][name]["business_sha256"] == expected["business_sha256"]
        parquet = pq.ParquetFile(ANALYTICS / (name + ".parquet"))
        assert parquet.metadata.num_rows == expected["rows"]
        assert parquet.schema_arrow.names == expected["columns"]
        hashes = []
        for group in range(parquet.num_row_groups):
            rows = parquet.read_row_group(group).to_pandas()
            assert len(rows) == parquet.metadata.row_group(group).num_rows
            hashes.extend(typed_hash(row, expected["kinds"]) for row in rows.itertuples(index=False, name=None))
        actual = hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest()
        assert actual == expected["business_sha256"], name
        checks[name] = dict(rows=parquet.metadata.num_rows, rowGroups=parquet.num_row_groups,
                            businessSha256=actual, reconciledWithFabric=True)
        print("Verified", name, checks[name]["rows"], flush=True)
    return checks, remote["source_publication"][0]


def fetch_geo(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        raw = response.read()
        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
    value = json.loads(raw)
    assert value["type"] == "FeatureCollection"
    return value, dict(url=url, downloadedAt=datetime.now(timezone.utc).isoformat(),
                       responseSha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def export_geometry(cities, refresh):
    metadata = OUT / "geometry-provenance.json"
    if metadata.exists() and not refresh:
        result = read_json(metadata)
        assert result["municipalityCount"] == len(cities)
        assert (OUT / result["statesFile"]).exists()
        assert all((OUT / result["cityFiles"].replace("{uf}", s["uf"])).exists() for s in STATES)
        return result
    base = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR"
    query = "?formato=application/vnd.geo%2Bjson&qualidade=intermediaria&intrarregiao="
    state_geo, state_source = fetch_geo(base + query + "UF")
    assert {f["properties"]["codarea"] for f in state_geo["features"]} == {s["id"] for s in STATES}
    write_json(OUT / "brazil-states.geojson", state_geo)
    city_geo, city_source = fetch_geo(base + query + "municipio")
    observed = {c["id"]: c for c in cities}
    selected = [f for f in city_geo["features"] if f["properties"]["codarea"] in observed]
    assert {f["properties"]["codarea"] for f in selected} == set(observed)
    for state in STATES:
        features = [f for f in selected if observed[f["properties"]["codarea"]]["uf"] == state["uf"]]
        write_json(OUT / "municipalities" / (state["uf"] + ".geojson"),
                   dict(type="FeatureCollection", features=features))
    result = dict(statesFile="brazil-states.geojson", cityFiles="municipalities/{uf}.geojson",
                  stateSource=state_source, municipalitySource=city_source,
                  municipalityCount=len(selected), geometryEdits="None; official intermediaria simplification preserved",
                  identifierProperty="codarea", documentation="https://servicodados.ibge.gov.br/api/docs/malhas?versao=3",
                  period="API default snapshot; boundaries do not reconstruct historical changes")
    write_json(metadata, result)
    return result


def records(frame, columns, week_indexes):
    result = []
    for row in frame[columns].itertuples(index=False, name=None):
        item = {}
        for key, value in zip(columns, row):
            if key == "w": value = week_indexes[str(value)[:10]]
            elif isinstance(value, Decimal): value = float(value)
            elif pd.isna(value): value = None
            elif key in {"n", "c"}: value = int(value)
            elif key == "eligible": value = bool(value)
            item[key] = value
        result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-geography", action="store_true")
    args = parser.parse_args()
    checks, receipt = verify_sources()
    con = duckdb.connect()
    for name in ["posto_semana", "referencia_uf_semana", "municipio_semana"]:
        con.read_parquet(str(ANALYTICS / (name + ".parquet"))).create_view(name)
    con.read_parquet(str(PUBLICATION / "weekly.parquet")).create_view("weekly")
    con.read_parquet(str(ROOT / "data/artifacts/context/municipal_seats.parquet")).create_view("seats")
    totals = con.sql("SELECT count(distinct cnpj), count(distinct municipio_ibge), sum(coletas), count(*) FROM posto_semana").fetchone()
    assert totals == (13030, 462, 2125547, 2125498), totals
    assert con.sql("SELECT sum(coletas) FROM weekly").fetchone()[0] == 2125547
    assert con.sql("SELECT count(*) FROM posto_semana WHERE moeda != 'BRL'").fetchone()[0] == 0
    weeks = [str(r[0]) for r in con.sql("SELECT DISTINCT inicio_semana_iso FROM weekly ORDER BY 1").fetchall()]
    assert len(weeks) == 131 and weeks[0] == "2024-01-01" and weeks[-1] == "2026-06-29"
    week_indexes = {w: i for i,w in enumerate(weeks)}
    city_frame = con.sql("""SELECT DISTINCT p.municipio_ibge AS id, s.municipio AS name,
        s.uf, s.latitude AS lat, s.longitude AS lon FROM posto_semana p
        JOIN seats s ON p.municipio_ibge=s.municipio_ibge ORDER BY id""").df()
    assert len(city_frame) == 462 and city_frame.notna().all().all()
    cities = city_frame.to_dict(orient="records")
    geometry = export_geometry(cities, args.refresh_geography)
    con.register("state_metadata", pd.DataFrame(STATES))
    con.sql("""CREATE VIEW raw_state AS SELECT s.uf, w.produto, w.unidade, w.inicio_semana_iso AS w,
        sum(w.coletas)::BIGINT AS c, min(preco_minimo) AS lo, max(preco_maximo) AS hi
        FROM weekly w JOIN state_metadata s ON substr(w.municipio_ibge,1,2)=s.id GROUP BY ALL""")
    con.sql("""CREATE VIEW raw_national AS SELECT produto, unidade, inicio_semana_iso AS w,
        sum(coletas)::BIGINT AS c, min(preco_minimo) AS lo, max(preco_maximo) AS hi
        FROM weekly GROUP BY ALL""")
    exports = []
    for slug, label, source, unit in PRODUCTS:
        # Product names are fixed constants above, never user input.
        states = con.execute("""SELECT r.inicio_semana_iso AS w, r.uf, r.mediana_uf AS p,
            r.postos_referencia AS n, a.c, a.lo, a.hi, r.postos_referencia>=10 AS eligible
            FROM referencia_uf_semana r JOIN raw_state a ON r.uf=a.uf AND r.produto=a.produto
            AND r.unidade=a.unidade AND r.inicio_semana_iso=a.w WHERE r.produto=? ORDER BY w,r.uf""", [source]).df()
        municipal = con.execute("""SELECT r.inicio_semana_iso AS w, r.municipio_ibge AS id,
            r.mediana_municipio AS p, r.postos_municipio AS n, a.coletas AS c,
            a.preco_minimo AS lo, a.preco_maximo AS hi, r.mediana_uf AS ref, r.benchmark_elegivel AS eligible
            FROM municipio_semana r JOIN weekly a ON r.municipio_ibge=a.municipio_ibge
            AND r.produto=a.produto AND r.unidade=a.unidade AND r.inicio_semana_iso=a.inicio_semana_iso
            WHERE r.produto=? ORDER BY w,id""", [source]).df()
        national = con.execute("""WITH medians AS (SELECT inicio_semana_iso AS w, produto, unidade,
            median(preco_mediano) AS p, count(*) AS n, count(distinct cnpj) AS distinct_stations
            FROM posto_semana WHERE comparacao_valida GROUP BY ALL)
            SELECT m.w,m.p,m.n,a.c,a.lo,a.hi FROM medians m JOIN raw_national a
            ON m.w=a.w AND m.produto=a.produto AND m.unidade=a.unidade
            WHERE m.produto=? AND m.n=m.distinct_stations ORDER BY w""", [source]).df()
        assert len(national) == 131
        assert int(states.c.sum()) == int(municipal.c.sum()) == int(national.c.sum())
        assert int(states.n.sum()) == int(municipal.n.sum()) == int(national.n.sum())
        assert len(states) == con.execute("SELECT count(*) FROM referencia_uf_semana WHERE produto=?", [source]).fetchone()[0]
        assert len(municipal) == con.execute("SELECT count(*) FROM municipio_semana WHERE produto=?", [source]).fetchone()[0]
        for frame in [states, municipal, national]:
            assert frame.notna().all().all() and (frame.lo <= frame.p).all() and (frame.p <= frame.hi).all()
        payload = dict(id=slug, unit=unit,
                       states=records(states, ["w","uf","p","n","c","lo","hi","eligible"], week_indexes),
                       cities=records(municipal, ["w","id","p","n","c","lo","hi","ref","eligible"], week_indexes),
                       national=records(national, ["w","p","n","c","lo","hi"], week_indexes))
        file = "products/" + slug + ".json"
        write_json(OUT / file, payload)
        exports.append(dict(id=slug, label=label, source=source, unit=unit, file=file,
                            stateRows=len(states), cityRows=len(municipal), bytes=(OUT/file).stat().st_size,
                            sha256=hashlib.sha256((OUT/file).read_bytes()).hexdigest()))
        print("Exported", slug, len(states), len(municipal), flush=True)
    assert sum(p["stateRows"] for p in exports) == 19808
    assert sum(p["cityRows"] for p in exports) == 252391
    manifest = dict(dataset=dict(title="Levantamento de preços ANP — snapshot validado no Fabric",
        periodStart="2024-01-01", periodEnd="2026-06-30", snapshotAt=receipt["published_at_utc"].replace(" ", "T") + "Z",
        observations=2125547, stations=13030, municipalities=462, publicationHash=receipt["source_sha256"],
        publicationId=receipt["snapshot_id"], notes=[
            "Snapshot histórico estático; não são preços em tempo real.",
            "Mediana por posto/semana; cada posto tem um peso na mediana regional e nacional.",
            "Referência da UF exige 10 postos; comparação municipal exige 3 postos e UF elegível.",
            "Contagens e extremos preservam todas as coletas aceitas, inclusive preços positivos incomuns.",
            "Pontos são sedes municipais do IBGE; não representam a localização de postos.",
            "Sem dado não equivale a preço zero; a última semana cobre somente 29–30/06/2026.",
            "Valores em BRL nominais; litro e m³ não são misturados.",
            "Malha IBGE simplificada consultada no snapshot; não reconstitui mudanças históricas de limites."]),
        weeks=weeks, products=exports, states=STATES, cities=cities, geometry=geometry,
        methodology=dict(national="Mediana dos preços medianos semanais de postos com comparação válida; um peso por posto/semana",
            collections="c: total de coletas aceitas; lo/hi: extremos brutos da publicação semanal",
            stationCount="n: postos distintos com comparação válida naquele produto/local/semana; não é contagem cumulativa",
            cityCoordinates="Sedes oficiais IBGE Localidades do Brasil 2022, SIRGAS 2000 (EPSG:4674)",
            eligibility="UF: n>=10. Município: n>=3 e referência da UF com >=10 postos."),
        sourceVerification=checks)
    write_json(OUT / "manifest.json", manifest)
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "validation.json")
    validation = dict(status="passed", exportedAt=datetime.now(timezone.utc).isoformat(),
        observations=2125547, stationWeeks=2125498, stateWeeks=19808, cityWeeks=252391,
        weeks=len(weeks), states=len(STATES), municipalities=len(cities), allSourceRowsFingerprintMatched=True,
        allProductCountSumsMatched=True, allPricesWithinRawExtrema=True,
        sources=checks, payloadFiles=len(files), payloadBytes=sum(p.stat().st_size for p in files),
        payloadGzipBytes=sum(len(gzip.compress(p.read_bytes(), mtime=0)) for p in files))
    write_json(OUT / "validation.json", validation)
    print(json.dumps(validation, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
