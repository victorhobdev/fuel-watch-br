"""Executa e acompanha um notebook no workspace de reconstrução da Fase 2."""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from client import ROOT, request
from evidence import write_json


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["start", "watch"])
    parser.add_argument("--notebook", required=True)
    parser.add_argument("--run-key")
    parser.add_argument("--parameters-file", type=Path)
    parser.add_argument("--job-id")
    return parser.parse_args()


def main():
    args = parse_args()
    rebuild_root = ROOT / ".local/phase2-rebuild"
    binding = json.loads((rebuild_root / "binding.json").read_text(encoding="utf-8"))
    notebook_id = binding["notebooks"][args.notebook]
    workspace_id = binding["workspace_id"]
    lakehouse_id = binding["lakehouse"]["id"]
    jobs_root = rebuild_root / "jobs"
    jobs_root.mkdir(parents=True, exist_ok=True)

    if args.mode == "start":
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.run_key or ""):
            raise ValueError("--run-key precisa conter apenas letras, números, _ e -")
        if not args.parameters_file:
            raise ValueError("Informe --parameters-file com o array de parâmetros do notebook")
        parameters_path = args.parameters_file.resolve()
        if not parameters_path.is_relative_to(rebuild_root.resolve()):
            raise ValueError("O arquivo de parâmetros deve ficar em .local/phase2-rebuild")
        parameters = json.loads(parameters_path.read_text(encoding="utf-8"))
        if not isinstance(parameters, list) or any(
            not isinstance(item, dict)
            or not {"name", "type", "value"}.issubset(item)
            for item in parameters
        ):
            raise ValueError("Parâmetros devem ser um array de objetos name/type/value")

        for item_id in binding["notebooks"].values():
            sessions = request(
                "GET",
                f"workspaces/{workspace_id}/notebooks/{item_id}/livySessions",
            ).json()
            if sessions.get("continuationToken"):
                raise RuntimeError("Paginar as sessões Livy antes de iniciar Spark")
            active = [
                session
                for session in sessions.get("value", [])
                if session.get("state") not in {"Succeeded", "Failed", "Cancelled", "Dead", "Error", "Success"}
            ]
            if active:
                raise RuntimeError(f"Spark ativo no workspace; aguardar antes do start: {item_id}")

        pending_path = jobs_root / f"{args.run_key}.pending.json"
        accepted_path = jobs_root / f"{args.run_key}.accepted.json"
        if pending_path.exists() or accepted_path.exists():
            raise FileExistsError("Tentativa registrada; inspecione o job antes de iniciar outro")
        write_json(pending_path, {"run_key": args.run_key, "started_at_utc": utc_now()})

        body = {
            "executionData": {
                "compute": "Spark",
                "computeConfiguration": {
                    "defaultLakehouse": {
                        "referenceType": "ById",
                        "itemId": lakehouse_id,
                        "workspaceId": workspace_id,
                    }
                },
            },
            "parameters": parameters,
        }
        path = (
            f"workspaces/{workspace_id}/notebooks/{notebook_id}"
            "/jobs/execute/instances?beta=false"
        )
        response = request("POST", path, body)
        if response.status_code != 202:
            raise RuntimeError(f"Resposta de submissão inesperada: HTTP {response.status_code}")
        location = response.headers["Location"]
        job_id = location.rstrip("/").split("/")[-1]
        retry_after = int(response.headers.get("Retry-After", "60"))
        write_json(
            accepted_path,
            {
                "run_key": args.run_key,
                "workspace_id": workspace_id,
                "notebook_id": notebook_id,
                "notebook": args.notebook,
                "job_id": job_id,
                "accepted_at_utc": utc_now(),
                "retry_after_seconds": retry_after,
                "parameter_names": [p["name"] for p in parameters],
            },
        )
        pending_path.unlink()
        print(json.dumps({"status": "Accepted", "job_id": job_id, "retry_after_seconds": retry_after}))
    else:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", args.job_id or ""):
            raise ValueError("--job-id precisa ser o UUID retornado pelo Fabric")
        job_id = args.job_id
        accepted_path = next(
            (
                path
                for path in jobs_root.glob("*.accepted.json")
                if json.loads(path.read_text(encoding="utf-8")).get("job_id") == job_id
            ),
            None,
        )
        if accepted_path is None:
            raise FileNotFoundError("Job sem recibo local de submissão; não inferir nem reenviar")
        accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
        if accepted["notebook_id"] != notebook_id:
            raise ValueError("--notebook não corresponde ao notebook da tentativa")

    run_path = (
        f"workspaces/{workspace_id}/notebooks/{notebook_id}"
        f"/jobs/execute/instances/{job_id}?beta=true"
    )
    retry_after = 60
    while True:
        time.sleep(retry_after)
        result = request("GET", run_path).json()
        properties = result.get("properties") or {}
        details = properties.get("computeDetails") or {}
        monitoring = details.get("monitoringInfo") or {}
        activity = monitoring.get("activityDetails") or {}
        evidence = {
            "status": result.get("status"),
            "environment": "fabric_rebuild",
            "workspace_id": workspace_id,
            "lakehouse_id": lakehouse_id,
            "notebook": args.notebook,
            "notebook_id": notebook_id,
            "job_id": job_id,
            "job_type": result.get("jobType"),
            "root_activity_id": result.get("rootActivityId"),
            "started_at_utc": result.get("startTimeUtc"),
            "ended_at_utc": result.get("endTimeUtc"),
            "failure_reason": result.get("failureReason"),
            "exit_value": properties.get("exitValue"),
            "compute": properties.get("compute"),
            "livy_id": details.get("livyId"),
            "spark_application_id": activity.get("sparkApplicationId"),
            "runtime_version": activity.get("runtimeVersion"),
            "checked_at_utc": utc_now(),
        }
        private_path = jobs_root / f"{job_id}.result.private.json"
        write_json(private_path, result)
        evidence_path = ROOT / "evidence/phase2/deployment" / f"rebuild-notebook-{accepted_path.stem.replace('.accepted', '') if args.mode == 'watch' else args.run_key}.json"
        write_json(evidence_path, evidence)
        print(json.dumps({"job_id": job_id, "status": evidence["status"], "failure_reason": evidence["failure_reason"]}, ensure_ascii=False), flush=True)
        if evidence["status"] in {"Completed", "Failed", "Cancelled", "Deduped"}:
            break
        retry_after = 30


if __name__ == "__main__":
    main()
