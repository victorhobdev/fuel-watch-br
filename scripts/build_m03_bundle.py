"""Gera entradas sintéticas preservadas, pacote de regras e notebook 05 importável."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile

from fuelwatch.m02_reference import iqr_fences
from fuelwatch.versioning_lab import SCOPE, apply_delivery, delivery, prepare_cases

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/artifacts/m03_fabric"


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def scenarios():
    """Oracle local gera expectativas; o notebook decide novamente em Spark/Delta."""
    from decimal import Decimal

    state = {"active": {}, "versions": {}}
    cases = prepare_cases()
    plan = []

    def add(name, case=None, delta=None, manifest=None, payload=None, complete=True, inject=False):
        nonlocal state
        previous = state["active"].get(SCOPE["scope_id"], {}).get("source_sha256")
        if manifest is None:
            manifest, payload = delivery(SCOPE, cases[case], previous, delta, complete)
        candidate, audit = apply_delivery(state, SCOPE, manifest, payload, name)
        if inject:
            if audit["status"] != "published_in_local_model":
                raise ValueError("Falha deve ocorrer após validar uma candidata publicável")
            status, reason = "failed_before_promotion", "injected_before_promotion"
        else:
            state = candidate
            status = {"published_in_local_model": "published"}.get(audit["status"], audit["status"])
            reason = audit.get("reason")
        active = state["active"].get(SCOPE["scope_id"])
        rows = deepcopy(active["rows"]) if active else []
        if rows:
            low, high = iqr_fences([Decimal(r["preco_venda"]) for r in rows])
            for row in rows:
                row["preco_incomum_iqr"] = not low <= Decimal(row["preco_venda"]) <= high
        plan.append({"name": name, "manifest": manifest, "csv_utf8": payload.decode("utf-8"),
                     "inject_before_promotion": inject, "expected_status": status,
                     "expected_reason": reason, "expected_active_rows": rows,
                     "expected_active_sha256": active["source_sha256"] if active else None})
        return manifest, payload

    base_manifest, base_bytes = add("base", "base", {"inserted": 4, "removed": 0, "updated": 0})
    add("replay_base", manifest=base_manifest, payload=base_bytes)
    for name, delta in [("correction_january", {"inserted": 0, "removed": 0, "updated": 1}),
                        ("late_arrival", {"inserted": 1, "removed": 0, "updated": 0}),
                        ("removed_row", {"inserted": 0, "removed": 1, "updated": 0}),
                        ("exact_duplicate", {"inserted": 0, "removed": 0, "updated": 0})]:
        add(name, name, delta)
    for name in ["conflict", "invalid", "empty"]:
        add(name, name)
    add("partial", "removed_row", complete=False)
    partial_rows = cases["removed_row"][:1]
    previous = state["active"][SCOPE["scope_id"]]["source_sha256"]
    manifest, payload = delivery(SCOPE, partial_rows, previous, None)
    add("unapproved_removal", manifest=manifest, payload=payload)
    add("stale_base", manifest=base_manifest, payload=base_bytes)
    manifest, payload = delivery(SCOPE, cases["removed_row"], previous, None)
    manifest["sha256"] = "0" * 64
    add("bad_hash", manifest=manifest, payload=payload)
    manifest, _ = delivery(SCOPE, cases["removed_row"], previous, None)
    payload = b"wrong;header\n1;2\n"
    manifest["sha256"] = sha(payload)
    add("bad_layout", manifest=manifest, payload=payload)
    add("retry_correct_hash", "removed_row", {"inserted": 0, "removed": 0, "updated": 0})
    cases["recovery"] = deepcopy(cases["removed_row"])
    cases["recovery"][0]["Valor de Venda"] = "6,40"
    manifest, payload = add("fail_before_promotion", "recovery",
                            {"inserted": 0, "removed": 0, "updated": 1}, inject=True)
    add("retry_after_failure", manifest=manifest, payload=payload)
    return plan


def build_bundle(output=OUTPUT):
    output.mkdir(parents=True, exist_ok=True)
    plan = {"is_synthetic": True, "scope": SCOPE, "scenarios": scenarios()}
    (output / "scenarios.json").write_bytes((json.dumps(plan, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    with zipfile.ZipFile(output / "fuelwatch_rules.zip", "w") as archive:
        for name in ["__init__.py", "contract.py", "m02_reference.py", "silver_spark.py"]:
            item = zipfile.ZipInfo("fuelwatch/" + name, date_time=(2026, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, (ROOT / "fuelwatch" / name).read_bytes())
    scope = json.loads((ROOT / "config/slice.json").read_text(encoding="utf-8"))
    profile = json.loads((ROOT / "evidence/source-profile.json").read_text(encoding="utf-8"))
    files = {}
    for name in ["fuelwatch_rules.zip", "scenarios.json"]:
        content = (output / name).read_bytes()
        files[name] = {"sha256": sha(content), "bytes": len(content)}
    manifest = {"bundle_version": "m03-v1", "is_synthetic": True, "scope": SCOPE,
                "scenario_count": len(plan["scenarios"]), "files": files,
                "official_guard": {"table": "silver_preco_coletado", "scope": scope,
                                   "source_sha256": profile["sources"]["anp"]["sha256"],
                                   "ibge_sha256": profile["sources"]["ibge"]["sha256"],
                                   "rows": 8052, "stations": 502, "municipalities": 27}}
    content = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (output / "manifest.json").write_bytes(content)
    return manifest, sha(content)


def build_notebook(manifest_sha):
    def cell(kind, source):
        result = {"cell_type": kind, "metadata": {}, "source": source.splitlines(keepends=True)}
        if kind == "code":
            result.update({"execution_count": None, "outputs": []})
        return result

    markdown = """# M03 — Versões, correção antiga e recuperação

**PREPARADO; execução Fabric ainda não validada.** Importar este notebook como notebook 05.
Anexar `lh_fuelwatch` como Lakehouse padrão e usar uma sessão nova após parar o 04.
Enviar os três arquivos de `data/artifacts/m03_fabric` para `Files/m03_input`, sem extrair o ZIP.

Executar **Run all**. O notebook executa 17 tentativas sintéticas em sequência e compara registros
com expectativas locais independentes. Uma falha injetada antes da promoção é esperada e tratada;
uma falha inesperada interrompe a execução. Todas as escritas de tabelas usam o prefixo `lab_m03_`.
A Silver oficial é lida, fixada por versão Delta e conferida ao final; nunca é alvo de escrita.
Cada Run all cria um experiment_id novo: conserva execuções anteriores e inclui repetição no próprio ensaio.
Não executar duas instâncias em paralelo. Este exercício não comprova publicação concorrente nem
implementa ainda promoção de republicações oficiais. Não instalar bibliotecas na sessão.
"""
    params = ('p_bundle_dir = "/lakehouse/default/Files/m03_input"\n'
              f'p_expected_manifest_sha256 = "{manifest_sha}"\n')
    cells = [cell("markdown", markdown), cell("code", params),
             cell("code", (ROOT / "notebooks/m02_sources/bootstrap.py").read_text(encoding="utf-8")),
             cell("markdown", "## Executar o laboratório\n\nOs prints `m03_scenario_verified` mostram o avanço. Ao final, enviar o JSON `m03_lab_validated`. As auditorias ficam em `Files/audit/m03/<experiment_id>/`."),
             cell("code", (ROOT / "notebooks/m03_sources/05_source_versions_backfill.py").read_text(encoding="utf-8"))]
    cells[1]["metadata"]["tags"] = ["parameters"]
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Synapse PySpark",
                "language": "python", "name": "synapse_pyspark"}, "language_info": {"name": "python"}},
                "nbformat": 4, "nbformat_minor": 4}
    (ROOT / "notebooks/05_source_versions_backfill.ipynb").write_text(
        json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    manifest, fingerprint = build_bundle()
    build_notebook(fingerprint)
    print(json.dumps({"status": "prepared_not_fabric_executed", "manifest_sha256": fingerprint,
                      "scenario_count": manifest["scenario_count"], "upload": OUTPUT.relative_to(ROOT).as_posix()}))
