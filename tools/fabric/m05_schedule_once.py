"""Janela curta e intervalo maior que a janela: um unico disparo pretendido."""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

from client import ROOT, request

parser = argparse.ArgumentParser()
parser.add_argument("--cases", required=True, help="Recovery-cases concluido e verificado")
args = parser.parse_args()
cases = json.loads((ROOT / args.cases).read_text(encoding="utf-8"))
assert cases["status"] == "recovery_and_replay_verified"
config = json.loads((ROOT / ".local/fabric-environment.json").read_text())
base = f"workspaces/{config['workspace_id']}/items/{config['pipeline_id']}/jobs"
report_path = ROOT / ".local/m05-api/schedule-once.json"
if report_path.exists():
    raise RuntimeError("Experimento ja registrado: inspecionar agenda e job existentes; nao criar outra agenda")
before = request("GET", base + "/instances").json()["value"]
assert all(job["status"] in {"Completed", "Failed", "Cancelled", "Deduped"} for job in before)
schedules = request("GET", base + "/Pipeline/schedules").json()["value"]
assert not any(schedule["enabled"] for schedule in schedules)
start = datetime.now(timezone.utc) + timedelta(minutes=2)
end = start + timedelta(minutes=5)
body = {"enabled": True, "configuration": {"startDateTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "localTimeZoneId": "UTC", "type": "Cron", "interval": 60},
        "executionData": {"pipelineName": "pl_fuelwatch_master", "parameters": {"p_fault_stage": "none"}}}
report = {"environment": "fabric", "request": body, "previous_job_ids": [job["id"] for job in before], "status": "creating"}


def save():
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


save()  # Inicio incerto nunca autoriza outro POST automatico.
created = request("POST", base + "/Pipeline/schedules", body).json()
report.update(schedule_id=created["id"], status="scheduled")
save()
schedule_path = base + "/Pipeline/schedules/" + created["id"]
job_id = None
try:
    while datetime.now(timezone.utc) < end + timedelta(minutes=3):
        jobs = request("GET", base + "/instances").json()["value"]
        added = [job for job in jobs if job["id"] not in report["previous_job_ids"]]
        if added:
            assert len(added) == 1 and added[0]["invokeType"] != "Manual", added
            job_id = added[0]["id"]
            report.update(job_id=job_id, invoke_type=added[0]["invokeType"], status="triggered")
            save()
            break
        print(json.dumps({"status": "waiting_for_scheduled_job", "schedule_id": created["id"]}), flush=True)
        time.sleep(30)
    if job_id is None:
        raise TimeoutError("Disparo nao observado: consultar o historico, nao repetir a agenda")
finally:
    disabled = dict(body, enabled=False)
    request("PATCH", schedule_path, disabled)
    actual = request("GET", schedule_path).json()
    assert actual["enabled"] is False
    report["disabled_verified"] = True
    save()

print(json.dumps({"job_id": job_id, "status": "schedule_disabled_before_monitoring_job"}), flush=True)
subprocess.run([sys.executable, str(ROOT / "tools/fabric/m05_job.py"), "--watch", job_id], check=True)
baseline = f".local/m05-api/runs/{cases['baseline_job']}/verification.json"
subprocess.run([sys.executable, str(ROOT / "tools/fabric/check_m05.py"), job_id, "--same-business-as", baseline], check=True)
assert not any(schedule["enabled"] for schedule in request("GET", base + "/Pipeline/schedules").json()["value"])
report["status"] = "scheduled_job_verified_and_schedule_disabled"
save()
print(json.dumps({"job_id": job_id, "status": report["status"]}), flush=True)
