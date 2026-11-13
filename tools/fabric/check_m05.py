"""Confere tentativa terminal usando job, atividades, recibos OneLake e Warehouse."""
import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal

from azure.storage.filedatalake import DataLakeServiceClient

from client import ROOT, credential
from warehouse import connect, results


def json_value(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    raise TypeError(type(value).__name__)


parser = argparse.ArgumentParser()
parser.add_argument("job_id")
parser.add_argument("--fault", choices=["none", "silver", "gold"], default="none")
parser.add_argument("--same-business-as", help="verification.json da tentativa anterior")
args = parser.parse_args()
folder = ROOT / ".local/m05-api/runs" / args.job_id
job = json.loads((folder / "job.json").read_text())
payload = json.loads((folder / "activities.json").read_text())
activities = payload.get("value", []) if isinstance(payload, dict) else payload
assert not isinstance(payload, dict) or not payload.get("continuationToken"), "Consultar pagina restante das atividades"
activity = {item["activityName"]: item for item in activities}
assert job["id"] == args.job_id
assert job["status"] == ("Completed" if args.fault == "none" else "Failed"), job
success = ["Capture_Baseline", "Copy_ANP", "Bronze"]
if args.fault != "silver":
    success += ["Silver", "Export_Gold_Input", "Import_Gold"]
if args.fault == "none":
    success += ["Publish_Gold", "Validate_Gold"]
for name in success:
    assert activity[name]["status"] == "Succeeded", name
if args.fault != "none":
    label = "Silver" if args.fault == "silver" else "Gold"
    failed = "Silver" if args.fault == "silver" else "Publish_Gold"
    assert activity[failed]["status"] == "Failed"
    assert activity["Guard_" + label + "_Failure"]["status"] == "Succeeded"
    assert activity["Fail_" + label]["status"] == "Failed"
    blocked = ["Export_Gold_Input", "Import_Gold", "Publish_Gold", "Validate_Gold"] if args.fault == "silver" else ["Validate_Gold"]
    assert all(name not in activity or activity[name]["status"] == "Skipped" for name in blocked)
    error_text = json.dumps(activity[failed].get("error"), ensure_ascii=False)
    assert ("M05_INJECTED_SILVER_FAILURE" if args.fault == "silver" else "51999") in error_text, error_text

config = json.loads((ROOT / ".local/fabric-environment.json").read_text())
fs = DataLakeServiceClient("https://onelake.dfs.fabric.microsoft.com", credential=credential).get_file_system_client(config["workspace_id"])
base = config["lakehouse_id"] + "/Files/"
receipts = []
for path in fs.get_paths(path=base + "audit/m05/" + args.job_id, recursive=True):
    if path.name.endswith(".json"):
        receipt = json.loads(fs.get_file_client(path.name).download_file().readall())
        assert receipt["root_run_id"] == args.job_id
        assert receipt["environment"] == "fabric"
        assert receipt["fault_stage"] == args.fault
        child_path = receipt.get("child_audit_relative_path")
        if child_path:
            child = json.loads(fs.get_file_client(base + child_path).download_file().readall())
            (folder / (receipt["phase"] + "-child.json")).write_text(json.dumps(child, indent=2), encoding="utf-8")
        receipts.append(receipt)
by_phase = {receipt["phase"]: receipt for receipt in receipts}
assert len(receipts) == (2 if args.fault == "silver" else 3)
assert by_phase["bronze"]["source_rows"] == 422418
assert by_phase["bronze"]["status"] == "stage_validated"
if args.fault == "silver":
    assert by_phase["silver"]["status"] == "failed"
else:
    assert by_phase["silver"]["status"] == by_phase["export"]["status"] == "stage_validated"

connection = connect()
try:
    cursor = connection.cursor()
    attempt = results(cursor.execute("SELECT * FROM m05.attempt WHERE root_run_id=?", args.job_id))[0]
    publication = results(cursor.execute("SELECT * FROM gold.publication"))[0]
    assert len(attempt) == len(publication) == 1
    if args.fault == "none":
        assert attempt[0]["status"] == "validated"
        assert attempt[0]["batch_id"] == publication[0]["batch_id"] == by_phase["export"]["batch_id"]
    else:
        guard = (ROOT / "data/artifacts/m05/warehouse/90_assert_unchanged.sql").read_text(encoding="utf-8").replace("{{ROOT_RUN_ID}}", args.job_id)
        results(cursor.execute(guard))  # THROW bloqueia a verificacao se houver qualquer diferenca.
    fingerprints = {}
    for table in ["published_business_bytes", "dim_posto", "dim_data", "dim_municipio", "dim_produto", "preco_semanal"]:
        rows = results(cursor.execute("SELECT * FROM gold." + table))[0]
        serialized = sorted(json.dumps(row, sort_keys=True, default=json_value, ensure_ascii=False) for row in rows)
        fingerprints[table] = {"rows": len(rows), "sha256": hashlib.sha256("\n".join(serialized).encode()).hexdigest()}
    assert fingerprints["published_business_bytes"]["rows"] == 8052
    assert fingerprints["dim_posto"]["rows"] == 518
    assert fingerprints["preco_semanal"]["rows"] == 656
    if args.same_business_as:
        previous = json.loads((ROOT / args.same_business_as).read_text(encoding="utf-8"))
        assert fingerprints == previous["business_fingerprints"], "Negocio mudou na repeticao/recuperacao"
finally:
    connection.close()

report = {"environment": "fabric", "job_id": args.job_id, "fault_stage": args.fault,
          "status": "m05_attempt_verified", "job_status": job["status"],
          "checked_at_utc": datetime.now(timezone.utc).isoformat(),
          "activities": [{key: item.get(key) for key in ["activityName", "status", "activityRunStart", "activityRunEnd", "durationInMs", "retryAttempt"]} for item in activities],
          "spark_sessions": [{"activity": item["activityName"], "session_id": item["output"]["result"].get("sessionId"),
                              "sharing": item["output"]["result"].get("highConcurrencyModeStatus")}
                             for item in activities if item.get("output") and "result" in item["output"]],
          "receipts": receipts, "warehouse_attempt": attempt, "publication": publication,
          "business_fingerprints": fingerprints,
          "previous_publication_unchanged": args.fault != "none",
          "same_business_as": args.same_business_as}
(folder / "verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=json_value), encoding="utf-8")
print(json.dumps({"job_id": args.job_id, "status": report["status"], "job_status": job["status"]}), flush=True)
