"""Wrapper serial: conserva notebooks aceitos e relaciona recibos ao Pipeline RunId."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

root_run = str(UUID(p_root_run_id))
if UUID(root_run).int == 0:
    raise ValueError("Pipeline RunId nao foi recebido; conferir celula de parametros")
if p_phase not in {"bronze", "silver", "export"}:
    raise ValueError("Fase desconhecida")
if p_fault_stage not in {"none", "silver", "gold"}:
    raise ValueError("Falha desconhecida")
if p_scope_id != "anp-2026-1-rj-gasolina":
    raise ValueError("Escopo ainda nao aprovado")
if p_source_sha256 != "a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c":
    raise ValueError("Nova versao exige revisao antes de promover")

files = Path("/lakehouse/default/Files")
attempt = str(uuid4())
receipt_dir = files / "audit/m05" / root_run / p_phase
receipt_dir.mkdir(parents=True, exist_ok=True)
receipt_path = receipt_dir / f"{attempt}.json"
receipt = {"root_run_id": root_run, "attempt_id": attempt, "phase": p_phase,
           "scope_id": p_scope_id, "source_sha256": p_source_sha256,
           "fault_stage": p_fault_stage, "environment": "fabric", "status": "started",
           "started_at_utc": datetime.now(timezone.utc).isoformat()}


def save():
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def child_summary(folder, notebook, expected_status, filename="summary.json"):
    """Execucao serial: exigir exatamente um recibo novo e bem-sucedido do filho."""
    directory = "Files/" + folder

    def receipts():
        if not notebookutils.fs.exists(directory):
            return set()
        return {folder + "/" + entry.name.rstrip("/") + "/" + filename
                for entry in notebookutils.fs.ls(directory) if entry.isDir
                if notebookutils.fs.exists(directory + "/" + entry.name.rstrip("/") + "/" + filename)}

    before = receipts()
    notebookutils.notebook.run(notebook, 900)
    added = receipts() - before
    if len(added) != 1:
        receipt["child_receipt_discovery"] = {"filename": filename, "before_count": len(before),
                                              "new_paths": sorted(added)}
        raise ValueError(f"Execucao filha sem recibo novo unico; filename={filename}; new_count={len(added)}")
    path = added.pop()
    result = json.loads(notebookutils.fs.head("Files/" + path, 1024 * 1024))
    if result.get("status") != expected_status or result.get("environment") != "fabric":
        raise ValueError("Recibo filho nao aprovado")
    receipt["child_audit_relative_path"] = path
    return result


save()
try:
    if p_phase == "bronze":
        child_run = f"{root_run}_{attempt}"
        landing = f"/lakehouse/default/Files/landing/anp/2026-1/{root_run}/ca-2026-01.zip"
        notebookutils.notebook.run("01_landing_to_bronze", 900, {
            "p_landing_zip": landing, "p_expected_zip_sha256": p_source_sha256, "p_run_id": child_run})
        path = files / "audit/anp" / f"{child_run}.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        if (result.get("status") != "bronze_validated" or result.get("source_sha256") != p_source_sha256
                or result.get("source_rows") != result.get("bronze_rows_for_version")):
            raise ValueError("Bronze sem reconciliacao aprovada")
        receipt.update(child_audit_relative_path=path.relative_to(files).as_posix(),
                       source_rows=result["source_rows"], child_run_id=child_run)
    elif p_phase == "silver":
        result = child_summary("audit/m03_official", "06_official_source_selection",
                               "m03_official_selection_validated")
        receipt["consumer_contract"] = result["consumer_contract"]
        if p_fault_stage == "silver":
            raise RuntimeError("M05_INJECTED_SILVER_FAILURE_AFTER_VALIDATION: bloquear export e Gold")
    else:
        result = child_summary("audit/m04", "07_export_gold_input", "m04_transfer_ready", "transfer.json")
        receipt.update(batch_id=result["batch_id"], source_delta_version=result["source_delta_version"],
                       snapshot_id=result["snapshot_id"])
    receipt.update(status="stage_validated", finished_at_utc=datetime.now(timezone.utc).isoformat())
    save()
except Exception as error:
    receipt.update(status="failed", error_type=type(error).__name__, error=str(error),
                   finished_at_utc=datetime.now(timezone.utc).isoformat())
    save()
    raise

print(json.dumps(receipt, ensure_ascii=False))
# exit fora de try/except: Fabric usa uma excecao propria para devolver o valor.
notebookutils.notebook.exit(json.dumps(receipt, ensure_ascii=False))
