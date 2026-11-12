"""Executa o modelo serial sintético M03 e preserva entradas, auditorias e estado local."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fuelwatch.versioning_lab import SCOPE, apply_delivery, delivery, prepare_cases

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def main():
    run_id = str(uuid4())
    started = datetime.now(timezone.utc).isoformat()
    output = ROOT / "data/artifacts/m03" / run_id
    output.mkdir(parents=True, exist_ok=False)
    cases = prepare_cases()
    protected = {"rows": [{"marker": "unchanged"}]}
    state = {"active": {"lab_m03_protected_scope": deepcopy(protected)}, "versions": {}}
    results = []
    base_manifest = base_payload = None

    def attempt(name, manifest, payload, expected_status, expected_delta=None, expected_reason=None):
        nonlocal state
        before = deepcopy(state["active"])
        candidate, audit = apply_delivery(state, SCOPE, manifest, payload, run_id + ":" + name)
        if audit["status"] != expected_status:
            raise ValueError(f"{name}: status inesperado {audit['status']}")
        if expected_reason and audit.get("reason") != expected_reason:
            raise ValueError(f"{name}: motivo inesperado {audit.get('reason')}")
        counts = {k: len(audit["delta"][k]) for k in ["inserted", "removed", "updated"]} if "delta" in audit else None
        if expected_delta is not None and counts != expected_delta:
            raise ValueError(f"{name}: diferenças inesperadas {counts}")
        if expected_status in ["rejected", "replayed"] and before != candidate["active"]:
            raise ValueError(f"{name}: alterou versão ativa sem publicação")
        if candidate["active"]["lab_m03_protected_scope"] != protected:
            raise ValueError(f"{name}: alterou outro escopo")
        audit["verified"] = {"expected_status": True, "protected_scope_unchanged": True,
                             "active_unchanged": before == candidate["active"]}
        folder = output / name
        folder.mkdir()
        (folder / "source.csv").write_bytes(payload)
        write_json(folder / "manifest.json", manifest)
        write_json(folder / "audit.json", audit)
        write_json(folder / "active-before.json", before)
        write_json(folder / "active-after.json", candidate["active"])
        results.append({"scenario": name, "status": audit["status"], "reason": audit.get("reason"),
                        "source_sha256": audit["source_sha256"], "delta_counts": counts,
                        "counts": audit.get("counts"), "verified": audit["verified"]})
        state = candidate

    changes = [("base", {"inserted": 4, "removed": 0, "updated": 0}),
               ("correction_january", {"inserted": 0, "removed": 0, "updated": 1}),
               ("late_arrival", {"inserted": 1, "removed": 0, "updated": 0}),
               ("removed_row", {"inserted": 0, "removed": 1, "updated": 0}),
               ("exact_duplicate", {"inserted": 0, "removed": 0, "updated": 0})]
    for name, delta in changes:
        previous = state["active"].get(SCOPE["scope_id"], {}).get("source_sha256")
        manifest, payload = delivery(SCOPE, cases[name], previous, delta)
        attempt(name, manifest, payload, "published_in_local_model", delta)
        if name == "base":
            base_manifest, base_payload = manifest, payload
            attempt("replay_base", manifest, payload, "replayed", {"inserted": 0, "removed": 0, "updated": 0})

    previous = state["active"][SCOPE["scope_id"]]["source_sha256"]
    for name in ["conflict", "invalid", "empty"]:
        manifest, payload = delivery(SCOPE, cases[name], previous, None)
        attempt(name, manifest, payload, "rejected", expected_reason="invalid_or_conflicting_or_empty_candidate")
    for complete, name, reason in [(False, "partial", "incomplete_snapshot"),
                                   (True, "unapproved_removal", "change_not_approved")]:
        manifest, payload = delivery(SCOPE, cases["removed_row"][:1], previous, None, complete)
        attempt(name, manifest, payload, "rejected", expected_reason=reason)
    attempt("stale_base", base_manifest, base_payload, "rejected", expected_reason="stale_selection")
    manifest, payload = delivery(SCOPE, cases["removed_row"], previous, None)
    manifest["sha256"] = "0" * 64
    attempt("bad_hash", manifest, payload, "rejected", expected_reason="hash_mismatch")
    manifest, _ = delivery(SCOPE, cases["removed_row"], previous, None)
    payload = b"wrong;header\n1;2\n"
    manifest["sha256"] = hashlib.sha256(payload).hexdigest()
    attempt("bad_layout", manifest, payload, "rejected", expected_reason="layout_mismatch")
    # Retry dos mesmos bytes após falha de hash: validação nova, sem alterar negócio.
    manifest, payload = delivery(SCOPE, cases["removed_row"], previous, {"inserted": 0, "removed": 0, "updated": 0})
    attempt("retry_correct_hash", manifest, payload, "published_in_local_model",
            {"inserted": 0, "removed": 0, "updated": 0})
    final = state["active"][SCOPE["scope_id"]]
    if len(final["rows"]) != 4 or max(r["data_coleta"] for r in final["rows"]) != "2026-06-30":
        raise ValueError("Estado final inesperado")
    write_json(output / "state.json", state)
    report = {"run_id": run_id, "environment": "local_synthetic_model_not_fabric", "is_synthetic": True,
              "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "local_versioning_lab_validated", "scope": SCOPE,
              "artifacts": output.relative_to(ROOT).as_posix(), "scenarios": results,
              "scenario_count": len(results), "final_rows": len(final["rows"]),
              "final_business_sha256": final["business_sha256"], "fabric_executed": False,
              "limits": ["Serial in-memory model; no distributed concurrency or Delta publication tested.",
                         "Fixtures are synthetic; no real ANP republication claimed.",
                         "approved_delta is a fixture expectation bound to candidate bytes, not external approval."]}
    evidence = ROOT / "evidence/m03"
    evidence.mkdir(parents=True, exist_ok=True)
    write_json(evidence / "local-lab.json", report)
    print(json.dumps({"status": report["status"], "scenarios": len(results), "final_rows": len(final["rows"]),
                      "artifacts": report["artifacts"], "fabric_executed": False}))


if __name__ == "__main__":
    main()
