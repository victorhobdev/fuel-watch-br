"""Empacota snapshots e regras já verificados; gera notebooks importáveis no Fabric."""

import hashlib
import json
from pathlib import Path
import zipfile

import pyarrow.parquet as pq

from fuelwatch.m02_reference import BUSINESS_FIELDS, decode_reference, iqr_fences
from fuelwatch.source import ROOT, source_record

OUTPUT = ROOT / "data/artifacts/m02"


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def build_bundle(output=OUTPUT):
    profile = json.loads((ROOT / "evidence/source-profile.json").read_text(encoding="utf-8"))
    proof = json.loads((ROOT / "evidence/local-slice.json").read_text(encoding="utf-8"))
    scope = json.loads((ROOT / "config/slice.json").read_text(encoding="utf-8"))
    if scope != proof["scope"] or proof["source_sha256"] != profile["sources"]["anp"]["sha256"]:
        raise ValueError("Escopo/hashes locais mudaram: revisar baseline antes de empacotar")
    ibge, payload = source_record(scope["ibge_source_id"])
    if ibge["sha256"] != proof["ibge_sha256"]:
        raise ValueError("Snapshot IBGE mais recente difere do baseline; usar versão aprovada")
    rows, _ = decode_reference(payload, ibge["sha256"])
    if len(rows) != 92:
        raise ValueError("Referência aprovada requer 92 municípios")
    reference_path = ROOT / proof["artifacts"] / "observacoes.parquet"
    reference = pq.read_table(reference_path)
    if reference.num_rows != 8052:
        raise ValueError("Parquet de referência não possui 8.052 coletas")
    actual_hashes = set(zip(reference.column("source_sha256").to_pylist(), reference.column("ibge_sha256").to_pylist()))
    if actual_hashes != {(proof["source_sha256"], proof["ibge_sha256"])}:
        raise ValueError("Parquet mistura snapshots diferentes")
    typed_rows = reference.to_pylist()
    keys = lambda r: (r["cnpj"], r["produto"], r["data_coleta"], r["unidade"])
    fields = ["cnpj", "produto", "data_coleta", "unidade", "preco_venda", "uf",
              "municipio_ibge", "revenda_observada", "bandeira_observada"]
    business = [{k: r[k] for k in fields} for r in sorted(typed_rows, key=keys)]
    if sha(json.dumps(business, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")) != proof["business_sha256"]:
        raise ValueError("Valores de negócio do Parquet divergem da prova local")
    if len({keys(r) for r in typed_rows}) != 8052 or len({r["cnpj"] for r in typed_rows}) != 502 or len({r["municipio_ibge"] for r in typed_rows}) != 27:
        raise ValueError("Chaves/cobertura do Parquet divergem da referência")
    low, high = iqr_fences(reference.column("preco_venda").to_pylist())
    if (str(low), str(high)) != (proof["iqr_lower"], proof["iqr_upper"]):
        raise ValueError("IQR da referência divergiu")
    if any(r["preco_incomum_iqr"] != (not low <= r["preco_venda"] <= high) for r in typed_rows):
        raise ValueError("Sinal IQR armazenado divergiu dos preços")
    output.mkdir(parents=True, exist_ok=True)
    (output / "municipios-rj.http.gz").write_bytes(payload)
    pq.write_table(reference.select(BUSINESS_FIELDS), output / "reference.parquet")
    modules = ["__init__.py", "contract.py", "m02_reference.py", "silver_spark.py"]
    with zipfile.ZipFile(output / "fuelwatch_rules.zip", "w") as archive:
        for name in modules:
            info = zipfile.ZipInfo("fuelwatch/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / "fuelwatch" / name).read_bytes())
    files = {}
    for name in ["fuelwatch_rules.zip", "municipios-rj.http.gz", "reference.parquet"]:
        content = (output / name).read_bytes()
        files[name] = {"sha256": sha(content), "bytes": len(content)}
    manifest = {
        "bundle_version": "m02-v1", "scope": scope,
        "anp": {"sha256": proof["source_sha256"], "csv_sha256": proof["csv_sha256"], "rows": 422418},
        "ibge": {"sha256": ibge["sha256"], "url": ibge["url"], "content_encoding": ibge["content_encoding"],
                 "retrieved_at_utc": profile["sources"]["ibge"]["started_at_utc"], "municipalities": 92},
        "reference": {"counts": proof["counts"], "stations": 502, "municipalities": 27,
                      "unusual_iqr_rows": 26, "iqr_lower": proof["iqr_lower"], "iqr_upper": proof["iqr_upper"],
                      "business_fields": BUSINESS_FIELDS, "local_business_sha256": proof["business_sha256"]},
        "files": files,
    }
    content = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "manifest.json").write_bytes(content)
    return manifest, sha(content)


def cell(kind, content, parameters=False):
    result = {"cell_type": kind, "metadata": {}, "source": content.splitlines(keepends=True)}
    if kind == "code":
        result.update({"execution_count": None, "outputs": []})
    if parameters:
        result["metadata"]["tags"] = ["parameters"]
    return result


def build_notebooks(manifest_sha):
    source = ROOT / "notebooks/m02_sources"
    params = ('p_bundle_dir = "/lakehouse/default/Files/m02_input"\n'
              f'p_expected_manifest_sha256 = "{manifest_sha}"\n')
    for name, title, instruction in [
        ("03_ibge_reference", "Snapshot IBGE → referência Delta", "Executar primeiro; conferir 92 municípios. Parar a sessão antes de abrir o notebook 04."),
        ("04_bronze_to_silver", "Bronze → Silver: gasolina/RJ", "Executar após o notebook 03. O fixture sintético grava somente lab_m02_quarantine; os dados oficiais vão para silver_preco_coletado. Reexecutar este notebook para verificar same_business_as_previous=true."),
    ]:
        markdown = f"# M02 — {title}\n\nPREPARADO; ainda não validado no Fabric. Anexar lh_fuelwatch como Lakehouse padrão.\n\n{instruction}\n\nFazer upload dos quatro arquivos de data/artifacts/m02 para Files/m02_input. O manifesto, o código e os snapshots serão conferidos por hash antes do uso. Os dados de referência são os snapshots oficiais preservados de 11/11/2026; este upload não representa uma nova chamada à API.\n"
        nb = {"cells": [cell("markdown", markdown), cell("code", params, True),
                        cell("code", (source / "bootstrap.py").read_text(encoding="utf-8")),
                        cell("code", (source / (name + ".py")).read_text(encoding="utf-8"))],
              "metadata": {"kernelspec": {"display_name": "Synapse PySpark", "language": "python", "name": "synapse_pyspark"},
                           "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 4}
        (ROOT / "notebooks" / (name + ".ipynb")).write_text(json.dumps(nb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    manifest, manifest_sha = build_bundle()
    build_notebooks(manifest_sha)
    print(json.dumps({"status": "prepared_locally_not_fabric_validated", "bundle": OUTPUT.relative_to(ROOT).as_posix(),
                      "manifest_sha256": manifest_sha, "files": {n: s["bytes"] for n, s in manifest["files"].items()}}, ensure_ascii=False))
