"""Inicia uma tentativa M05 ou acompanha a mesma tentativa, sem repetir POST."""
import argparse
import json
import time
from datetime import datetime, timedelta, timezone

from client import ROOT, request, environment_config

parser = argparse.ArgumentParser()
action = parser.add_mutually_exclusive_group(required=True)
action.add_argument("--start", choices=["none", "silver", "gold"])
action.add_argument("--watch", help="ID de uma tentativa ja iniciada")
args = parser.parse_args()
config = environment_config()
workspace, pipeline = config["workspace_id"], config["pipeline_id"]
base = f"workspaces/{workspace}/items/{pipeline}/jobs"

if args.start is not None:
    page = request("GET", base + "/instances").json()
    while True:
        if any(job["status"] not in {"Completed", "Failed", "Cancelled", "Deduped"} for job in page["value"]):
            raise RuntimeError("Existe job ativo; acompanhar antes de iniciar outro")
        if not page.get("continuationUri"):
            break
        page = request("GET", page["continuationUri"]).json()
    deadline = time.monotonic() + 600
    while True:
        sessions = request("GET", f"workspaces/{workspace}/notebooks/{config['notebook_stage_id']}/livySessions").json()
        active = [session for session in sessions["value"] if session["state"] not in {"Succeeded", "Failed", "Cancelled", "Dead", "Error", "Success"}]
        ended = [datetime.fromisoformat(session["endDateTime"].replace("Z", "+00:00"))
                 for session in sessions["value"] if session.get("endDateTime") and not session["endDateTime"].startswith("0001")]
        settle_seconds = max(0, 60 - (datetime.now(timezone.utc) - max(ended)).total_seconds()) if ended else 0
        if not active and settle_seconds == 0:
            break
        print(json.dumps({"status": "waiting_for_spark_release", "settle_seconds": round(settle_seconds), "sessions": [
            {"session_id": session["livyId"], "state": session["state"]} for session in active]}), flush=True)
        if time.monotonic() >= deadline:
            raise TimeoutError("Sessao Spark ainda ativa; nenhum novo pipeline foi iniciado")
        time.sleep(30)
    response = request("POST", base + "/Pipeline/instances", {
        "executionData": {"pipelineName": "pl_fuelwatch_master", "parameters": {"p_fault_stage": args.start}}})
    location = response.headers["Location"]
    job_id = location.rstrip("/").split("/")[-1]
    folder = ROOT / ".local/m05-api/runs" / job_id
    folder.mkdir(parents=True, exist_ok=False)
    accepted = {"job_id": job_id, "location": location, "fault_stage": args.start,
                "accepted_at_utc": datetime.now(timezone.utc).isoformat(),
                "retry_after": int(response.headers.get("Retry-After", "30"))}
    (folder / "accepted.json").write_text(json.dumps(accepted, indent=2))
    print(json.dumps(accepted), flush=True)
    time.sleep(accepted["retry_after"])
else:
    job_id = args.watch
    folder = ROOT / ".local/m05-api/runs" / job_id
    folder.mkdir(parents=True, exist_ok=True)

while True:
    state = request("GET", base + "/instances/" + job_id).json()
    (folder / "job.json").write_text(json.dumps(state, indent=2))
    now = datetime.now(timezone.utc)
    activities = request("POST", f"workspaces/{workspace}/datapipelines/pipelineruns/{job_id}/queryactivityruns", {
        "filters": [], "orderBy": [{"orderBy": "ActivityRunStart", "order": "ASC"}],
        "lastUpdatedAfter": (now - timedelta(days=2)).isoformat(),
        "lastUpdatedBefore": (now + timedelta(minutes=1)).isoformat()}).json()
    (folder / "activities.json").write_text(json.dumps(activities, indent=2))
    items = activities.get("value", []) if isinstance(activities, dict) else activities
    print(json.dumps({"job_id": job_id, "status": state["status"],
                      "activities": {item["activityName"]: item["status"] for item in items}}), flush=True)
    if state["status"] in {"Completed", "Failed", "Cancelled", "Deduped"}:
        break
    time.sleep(30)
