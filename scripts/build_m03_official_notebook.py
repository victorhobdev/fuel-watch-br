"""Notebook 06 reutiliza o pacote M02 aprovado; não gera nem altera esse pacote."""

import hashlib
import json
from pathlib import Path

from fuelwatch.publication import validate_publication_policy
from scripts.build_m02_bundle import cell

ROOT = Path(__file__).resolve().parents[1]


def reviewed_policy():
    folder = ROOT / "data/artifacts/m02"
    content = (folder / "manifest.json").read_bytes()
    approved = json.loads((ROOT / "evidence/m02/preparation.json").read_text(encoding="utf-8"))
    fingerprint = hashlib.sha256(content).hexdigest()
    if fingerprint != approved["bundle_manifest_sha256"]:
        raise ValueError("Pacote M02 difere do aprovado")
    manifest = json.loads(content)
    for name, spec in manifest["files"].items():
        data = (folder / name).read_bytes()
        if len(data) != spec["bytes"] or hashlib.sha256(data).hexdigest() != spec["sha256"]:
            raise ValueError("Arquivo M02 diferente do revisado")
    policy = {"policy_version": "official-initial-v1", "is_synthetic": False, "complete_snapshot": True,
              "scope": manifest["scope"], "source_id": manifest["scope"]["anp_source_id"],
              "source_sha256": manifest["anp"]["sha256"], "ibge_sha256": manifest["ibge"]["sha256"],
              "expected_previous_identity": None,
              "approved_delta": {"inserted": 8052, "removed": 0, "updated": 0}}
    validate_publication_policy(policy, manifest)
    return policy, fingerprint


def build():
    policy, fingerprint = reviewed_policy()
    intro = """# M03 — Seleção da versão oficial e repetição

**PREPARADO; ainda não executado no Fabric.** Importar como notebook 06 e anexar `lh_fuelwatch`
como Lakehouse padrão. Parar a sessão 05 e usar sessão nova, sem outro job de publicação em paralelo.

Reutiliza os quatro arquivos aprovados em `Files/m02_input`; não exige novos uploads de dados.
Confere os bytes oficiais preservados, a Bronze, a referência IBGE e a candidata Silver.
Publica somente o escopo revisado em `silver_preco_publicado`; essa tabela identifica a versão
ativa junto às coletas. Gold deverá consumir essa seleção fixada por versão Delta.

Run all faz o registro inicial (ou verifica uma seleção já existente) e uma repetição sem escrita
na tabela publicada. `silver_preco_coletado`, Bronze, referência IBGE e laboratórios não são alterados.
O snapshot selecionado é o já aprovado; não há nova captura nem republicação ANP reivindicada.
"""
    params = ('p_bundle_dir = "/lakehouse/default/Files/m02_input"\n'
              f'p_expected_manifest_sha256 = "{fingerprint}"\n'
              f'p_publication_policy = {policy!r}\n')
    source = ROOT / "notebooks/m03_sources/06_official_source_selection.py"
    notebook = {"cells": [cell("markdown", intro), cell("code", params, True),
                cell("code", (ROOT / "notebooks/m02_sources/bootstrap.py").read_text(encoding="utf-8")),
                cell("code", (ROOT / "fuelwatch/publication.py").read_text(encoding="utf-8")),
                cell("markdown", "## Conferir, selecionar e repetir\n\nEnviar o JSON final `m03_official_selection_validated`. Auditoria em `Files/audit/m03_official/<run_id>/`."),
                cell("code", source.read_text(encoding="utf-8"))],
                "metadata": {"kernelspec": {"display_name": "Synapse PySpark", "language": "python", "name": "synapse_pyspark"},
                             "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 4}
    path = ROOT / "notebooks/06_official_source_selection.ipynb"
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, policy, fingerprint


if __name__ == "__main__":
    path, policy, fingerprint = build()
    print(json.dumps({"status": "prepared_not_fabric_executed", "notebook": path.relative_to(ROOT).as_posix(),
                      "reuses_m02_manifest_sha256": fingerprint, "new_data_upload_required": False}))
