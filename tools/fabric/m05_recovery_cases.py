"""Ensaios seriais: para no primeiro resultado inesperado, sem retry de pipeline."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

from client import ROOT

parser = argparse.ArgumentParser()
parser.add_argument("--baseline-job", required=True, help="Tentativa normal ja concluida e verificada")
args = parser.parse_args()
baseline = ROOT / ".local/m05-api/runs" / args.baseline_job / "verification.json"
baseline_report = json.loads(baseline.read_text(encoding="utf-8"))
assert baseline_report["job_status"] == "Completed" and baseline_report["fault_stage"] == "none"
assert baseline_report["status"] == "m05_attempt_verified"
baseline_relative = baseline.relative_to(ROOT).as_posix()
experiment = ROOT / ".local/m05-api" / ("recovery-cases-" + str(uuid4()) + ".json")
report = {"environment": "fabric", "baseline_job": args.baseline_job, "cases": [],
          "started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "running"}


def save():
    experiment.write_text(json.dumps(report, indent=2), encoding="utf-8")


save()
try:
    for label, fault in [("silver_failure", "silver"), ("silver_recovery", "none"),
                         ("gold_failure", "gold"), ("gold_recovery", "none"), ("full_replay", "none")]:
        entry = {"case": label, "fault_stage": fault, "status": "starting"}
        report["cases"].append(entry)
        save()
        process = subprocess.Popen([sys.executable, str(ROOT / "tools/fabric/m05_job.py"), "--start", fault],
                                   stdout=subprocess.PIPE, text=True, encoding="utf-8")
        for line in process.stdout:
            print(line.rstrip(), flush=True)
            event = json.loads(line)
            if "job_id" in event:
                entry["job_id"] = event["job_id"]
                entry["status"] = event.get("status", "accepted")
                save()
        if process.wait() != 0:
            raise RuntimeError("Observacao interrompida; acompanhar o job registrado, nao iniciar outro")
        subprocess.run([sys.executable, str(ROOT / "tools/fabric/check_m05.py"), entry["job_id"],
                        "--fault", fault, "--same-business-as", baseline_relative], check=True)
        entry["status"] = "verified"
        save()
        print(json.dumps({"case": label, "job_id": entry["job_id"], "status": "verified"}), flush=True)
    report["status"] = "recovery_and_replay_verified"
except Exception as error:
    report.update(status="stopped", error_type=type(error).__name__, error=str(error))
    raise
finally:
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    save()
