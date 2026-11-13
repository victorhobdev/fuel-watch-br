"""Contrato do wrapper em simulacao local; nao comprova execucao no Fabric."""
import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

SOURCE = Path("notebooks/m05_sources/08_pipeline_stage.py").read_text(encoding="utf-8")
SHA = "a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c"


class StageContractTests(unittest.TestCase):
    def run_stage(self, phase, fault="none", child_status=None, child_raises=False, stale_mount=False, receipt_count=1):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            exited = []
            calls = []
            original_glob = Path.glob
            old = root / "audit/m04/old-batch/transfer.json"
            old.parent.mkdir(parents=True)
            old.write_text(json.dumps({"status": "m04_transfer_ready", "environment": "fabric", "batch_id": "old-batch"}))

            def mounted_glob(directory, pattern):
                if stale_mount and directory == root / "audit/m04":
                    return iter([])
                return original_glob(directory, pattern)

            def remote_path(path):
                return root / path.removeprefix("Files/")

            def remote_ls(path):
                return [SimpleNamespace(name=p.name, isDir=p.is_dir(), path=path.rstrip("/") + "/" + p.name)
                        for p in remote_path(path).iterdir()]

            def run(name, timeout, args=None):
                calls.append((name, args))
                if child_raises:
                    raise RuntimeError("child failed")
                if phase == "bronze":
                    target = root / "audit/anp" / (args["p_run_id"] + ".json")
                    summary = {"status": "bronze_validated", "source_sha256": SHA,
                               "source_rows": 422418, "bronze_rows_for_version": 422418}
                else:
                    target = root / ("audit/m03_official" if phase == "silver" else "audit/m04") / str(uuid4()) / ("summary.json" if phase == "silver" else "transfer.json")
                    summary = {"status": child_status or ("m03_official_selection_validated" if phase == "silver" else "m04_transfer_ready"),
                               "environment": "fabric", "consumer_contract": {"snapshot_id": "fixture"},
                               "batch_id": "new-batch", "source_delta_version": 0, "snapshot_id": "fixture"}
                for index in range(receipt_count):
                    output = target if index == 0 else target.parent.parent / str(uuid4()) / target.name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_text(json.dumps(summary), encoding="utf-8")

            values = {"p_root_run_id": str(uuid4()), "p_phase": phase, "p_fault_stage": fault,
                      "p_scope_id": "anp-2026-1-rj-gasolina", "p_source_sha256": SHA,
                      "notebookutils": SimpleNamespace(notebook=SimpleNamespace(run=run, exit=exited.append),
                          fs=SimpleNamespace(ls=remote_ls, exists=lambda p: remote_path(p).exists(),
                                             head=lambda p, size: remote_path(p).read_text(encoding="utf-8")))}
            error = None
            with contextlib.redirect_stdout(io.StringIO()), patch.object(Path, "glob", mounted_glob):
                try:
                    exec(compile(SOURCE.replace('Path("/lakehouse/default/Files")', f"Path({folder!r})"), "stage", "exec"), values)
                except Exception as caught:
                    error = caught
            receipts = [json.loads(p.read_text()) for p in root.glob("audit/m05/*/*/*.json")]
            return error, exited, calls, receipts

    def test_bronze_propagates_landing_hash_and_unique_child_attempt(self):
        error, exited, calls, receipts = self.run_stage("bronze")
        self.assertIsNone(error)
        self.assertEqual(receipts[0]["status"], "stage_validated")
        self.assertIn(receipts[0]["root_run_id"], calls[0][1]["p_landing_zip"])
        self.assertEqual(calls[0][1]["p_expected_zip_sha256"], SHA)
        self.assertEqual(json.loads(exited[0])["source_rows"], 422418)

    def test_silver_failure_records_child_and_does_not_return_success(self):
        error, exited, _, receipts = self.run_stage("silver", "silver")
        self.assertIn("M05_INJECTED_SILVER_FAILURE", str(error))
        self.assertFalse(exited)
        self.assertEqual(receipts[0]["status"], "failed")
        self.assertIn("child_audit_relative_path", receipts[0])

    def test_export_returns_exact_new_batch(self):
        error, exited, calls, receipts = self.run_stage("export")
        self.assertIsNone(error)
        self.assertEqual(json.loads(exited[0])["batch_id"], "new-batch")
        self.assertEqual(receipts[0]["status"], "stage_validated")
        self.assertTrue(receipts[0]["child_audit_relative_path"].endswith("/transfer.json"))
        self.assertEqual(calls[0][1]["p_rules_library_path"], "/lakehouse/default/Files/m02_input/fuelwatch_rules.zip")

    def test_remote_receipt_remains_discoverable_when_mounted_listing_is_stale(self):
        error, exited, _, receipts = self.run_stage("export", stale_mount=True)
        self.assertIsNone(error)
        self.assertEqual(json.loads(exited[0])["batch_id"], "new-batch")
        self.assertEqual(receipts[0]["status"], "stage_validated")

    def test_failed_or_missing_child_receipt_never_succeeds(self):
        for options in [{"child_status": "failed"}, {"child_raises": True}, {"receipt_count": 0}, {"receipt_count": 2}]:
            with self.subTest(options=options):
                error, exited, _, receipts = self.run_stage("export", **options)
                self.assertIsNotNone(error)
                self.assertFalse(exited)
                self.assertEqual(receipts[0]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
