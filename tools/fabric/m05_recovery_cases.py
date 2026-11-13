"""Ensaios seriais: para no primeiro resultado inesperado, sem retry de pipeline."""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

from client import ROOT


def resume_action(fault, previous):
    if previous is None:
        return "start"
    if previous["status"] == "verified":
        return "skip"
    if previous["status"] == "Cancelled":
        raise RuntimeError("Tentativa cancelada; revisar antes de executar novamente")
    if not previous.get("job_id"):
        raise RuntimeError("Inicio sem job_id: inspecionar historico antes de repetir POST")
    if previous["status"] == "Failed" and fault == "none":
        return "start"  # Falha terminal conhecida na recuperacao; nunca mero timeout de observacao.
    return "watch"


parser = argparse.ArgumentParser()
choice = parser.add_mutually_exclusive_group(required=True)
choice.add_argument("--baseline-job", help="Tentativa normal ja concluida e verificada")
choice.add_argument("--resume", help="Arquivo recovery-cases interrompido; preserva casos verificados")
args = parser.parse_args()
if args.resume:
    experiment = ROOT / args.resume
    report = json.loads(experiment.read_text(encoding="utf-8"))
    assert report["status"] == "stopped", "So retomar experimento interrompido"
    args.baseline_job = report["baseline_job"]
    report.setdefault("interruptions", []).append({key: report.get(key) for key in ["status", "error", "error_type", "finished_at_utc"]})
    for key in ["error", "error_type", "finished_at_utc"]:
        report.pop(key, None)
    report["status"] = "running"
    report["resumed_at_utc"] = datetime.now(timezone.utc).isoformat()
else:
    experiment = ROOT / ".local/m05-api" / ("recovery-cases-" + str(uuid4()) + ".json")
    report = {"environment": "fabric", "baseline_job": args.baseline_job, "cases": [],
              "started_at_utc": datetime.now(timezone.utc).isoformat(), "status": "running"}
baseline = ROOT / ".local/m05-api/runs" / args.baseline_job / "verification.json"
baseline_report = json.loads(baseline.read_text(encoding="utf-8"))
assert baseline_report["job_status"] == "Completed" and baseline_report["fault_stage"] == "none"
assert baseline_report["status"] == "m05_attempt_verified"
baseline_relative = baseline.relative_to(ROOT).as_posix()


def save():
    experiment.write_text(json.dumps(report, indent=2), encoding="utf-8")


save()
try:
    for label, fault in [("silver_failure", "silver"), ("silver_recovery", "none"),
                         ("gold_failure", "gold"), ("gold_recovery", "none"), ("full_replay", "none")]:
        previous = next((case for case in reversed(report["cases"]) if case["case"] == label), None)
        operation = resume_action(fault, previous)
        if operation == "skip":
            continue
        if operation == "watch":
            entry = previous
            command = ["--watch", entry["job_id"]]
        else:
            entry = {"case": label, "fault_stage": fault, "status": "starting"}
            report["cases"].append(entry)
            command = ["--start", fault]
        save()
        process = subprocess.Popen([sys.executable, str(ROOT / "tools/fabric/m05_job.py"), *command],
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
