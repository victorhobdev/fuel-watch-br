"""Dataflow Gen2: aplicacao da definicao e acompanhamento sem repetir inicio."""
import argparse
import base64
import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from client import ROOT, definition_operation, request

parser = argparse.ArgumentParser()
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--start", choices=["baseline", "replay", "invalid", "recovery"])
mode.add_argument("--watch")
args = parser.parse_args()
config = json.loads((ROOT / ".local/fabric-environment.json").read_text())
workspace, item = config["workspace_id"], config["dataflow_m06_id"]
base = f"workspaces/{workspace}/dataflows/{item}"
jobs = f"workspaces/{workspace}/items/{item}/jobs/instances"
output = ROOT / ".local/m06-api"
output.mkdir(exist_ok=True)

if args.start:
    for target in [item, config["pipeline_id"]]:
        history = request("GET", f"workspaces/{workspace}/items/{target}/jobs/instances").json()["value"]
        assert all(job["status"] in {"Completed", "Failed", "Cancelled", "Deduped"} for job in history), "Outro job ativo: aguardar"
    definition = definition_operation(base + "/getDefinition")
    backup = output / ("definition-before-" + str(uuid4()) + ".json")
    backup.write_text(json.dumps(definition, indent=2), encoding="utf-8")
    part = next(p for p in definition["definition"]["parts"] if p["path"] == "mashup.pq")
    source = base64.b64decode(part["payload"]).decode("utf-8")
    wanted = args.start == "invalid"
    old = "shared p_inject_invalid = " + ("false" if wanted else "true")
    new = "shared p_inject_invalid = " + ("true" if wanted else "false")
    assert old in source or new in source, "Parametro da fixture ausente"
    if old in source:
        source = source.replace(old, new, 1)
        part["payload"] = base64.b64encode(source.encode()).decode()
        definition_operation(base + "/updateDefinition", {"definition": definition["definition"]})
        readback = definition_operation(base + "/getDefinition")
        actual = base64.b64decode(next(p for p in readback["definition"]["parts"] if p["path"] == "mashup.pq")["payload"]).decode()
        assert new in actual and old not in actual
    response = request("POST", base + "/jobs/execute/instances", {"executionData": {"executeOption": "ApplyChangesIfNeeded"}})
    location = response.headers["Location"]
    job_id = location.rstrip("/").split("/")[-1]
    folder = output / job_id
    folder.mkdir(exist_ok=False)
    accepted = {"environment": "fabric", "job_id": job_id, "case": args.start, "fixture_invalid": wanted,
                "accepted_at_utc": datetime.now(timezone.utc).isoformat(), "definition_backup": backup.name,
                "retry_after": int(response.headers.get("Retry-After", "60"))}
    (folder / "accepted.json").write_text(json.dumps(accepted, indent=2))
    print(json.dumps(accepted), flush=True)
    time.sleep(accepted["retry_after"])
else:
    job_id = args.watch
    folder = output / job_id
    folder.mkdir(exist_ok=True)

while True:
    state = request("GET", jobs + "/" + job_id).json()
    (folder / "job.json").write_text(json.dumps(state, indent=2))
    print(json.dumps({"job_id": job_id, "status": state["status"], "failure_reason": state.get("failureReason")}), flush=True)
    if state["status"] in {"Completed", "Failed", "Cancelled", "Deduped"}:
        break
    time.sleep(30)
