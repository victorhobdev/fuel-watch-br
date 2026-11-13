"""Prepara fixtures isolados; nao concede papeis nem simula acesso do leitor."""
import base64
import json
import re
import time
from datetime import datetime, timezone

from azure.storage.filedatalake import DataLakeServiceClient

from client import ROOT, credential, request
from warehouse import connect, results

config = json.loads((ROOT / ".local/fabric-environment.json").read_text())
state_path = ROOT / ".local/m07-setup.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {"completed_sql_batches": []}


def save():
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


sql = (ROOT / "sql/labs/security.sql").read_text(encoding="utf-8")
batches = re.split(r"(?m)^GO\s*$", sql)
with connect(config) as connection:
    for index, batch in enumerate(batches):
        if index in state["completed_sql_batches"]:
            continue
        rows = results(connection.cursor().execute(batch))
        state["completed_sql_batches"].append(index)
        save()
        print("SQL batch accepted:", index, flush=True)
    context = results(connection.cursor().execute(
        "SELECT HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CONTROL') AS has_control; "
        "SELECT fixture_id,uf,preco_sintetico,contato_ficticio,is_synthetic "
        "FROM lab_m07.access_fixture ORDER BY fixture_id;"))
    assert context[0][0]["has_control"] == 1
    assert [row["uf"] for row in context[1]] == ["RJ", "SP"]
    assert context[1][0]["contato_ficticio"] == "rj@synthetic.invalid"

workspace, lakehouse = config["workspace_id"], config["lakehouse_id"]
if state.get("notebook_create_status") == 202 and "probe_notebook_id" not in state:
    location = state["notebook_create_location"]
    deadline = time.monotonic() + 300
    while True:
        operation = request("GET", location).json()
        assert operation["status"] != "Failed", operation
        if operation["status"] == "Succeeded":
            state["probe_notebook_id"] = request("GET", location.rstrip("/") + "/result").json()["id"]
            save()
            break
        assert time.monotonic() < deadline, "Operacao pendente: retomar o mesmo Location"
        time.sleep(10)
if "probe_notebook_id" not in state:
    items = request("GET", f"workspaces/{workspace}/items").json()["value"]
    matches = [item for item in items if item["displayName"] == "lab_m07_permission_probe"]
    assert len(matches) <= 1
    if matches:
        probe = matches[0]
        assert probe["type"] == "Notebook"
    else:
        notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
            "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
            "language_info": {"name": "python"}},
            "cells": [{"cell_type": "markdown", "metadata": {},
                       "source": ["Fixture sintetico M07: teste de autorizacao, sem execucao Spark."]}]}
        payload = base64.b64encode(json.dumps(notebook).encode()).decode()
        response = request("POST", f"workspaces/{workspace}/notebooks", {
            "displayName": "lab_m07_permission_probe", "description": "Synthetic authorization fixture; never executed",
            "definition": {"format": "ipynb", "parts": [{"path": "notebook-content.ipynb",
                            "payload": payload, "payloadType": "InlineBase64"}]}})
        # Preserve acceptance before inspecting a potentially asynchronous response.
        state["notebook_create_status"] = response.status_code
        state["notebook_create_location"] = response.headers.get("Location")
        save()
        if response.status_code == 202:
            raise SystemExit("Criacao aceita; execute novamente para acompanhar o mesmo Location, sem novo POST")
        assert response.status_code == 201
        probe = response.json()
    state["probe_notebook_id"] = probe["id"]
    save()

service = DataLakeServiceClient("https://onelake.dfs.fabric.microsoft.com", credential=credential)
filesystem = service.get_file_system_client(workspace)
directory = filesystem.get_directory_client(f"{lakehouse}/Files/lab_m07")
directory.create_directory()
file = directory.get_file_client("read_probe.json")
content = b'{"is_synthetic":true,"purpose":"M07 authorization fixture"}'
if not file.exists():
    file.create_file()
    file.append_data(content, offset=0, length=len(content))
    file.flush_data(len(content))
assert file.download_file().readall() == content
state["read_probe_path"] = f"{lakehouse}/Files/lab_m07/read_probe.json"
state["author_verified_at_utc"] = datetime.now(timezone.utc).isoformat()
save()

evidence = {"status": "author_fixtures_verified", "environment": "fabric",
            "verified_at_utc": state["author_verified_at_utc"], "synthetic_rows": 2,
            "author_visible_ufs": ["RJ", "SP"], "author_unmasked": True,
            "probe_notebook_created": True, "probe_file_readback_equal": True,
            "reader_tested": False, "roles_granted_by_setup": False}
out = ROOT / "evidence/fabric/security/author-setup-2026-11-13.json"
out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(json.dumps(evidence), flush=True)
