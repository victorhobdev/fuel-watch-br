import ast
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import nbformat

from scripts.build_m04_bundle import ROOT, build_bundle, setup
from scripts.prepare_m04_gold import literal
from fuelwatch.gold_input import select_m03_contract
from fuelwatch.m02_reference import BUSINESS_FIELDS


class M04PackageTests(unittest.TestCase):
    def test_sql_literals_preserve_null_and_quote_apostrophe(self):
        self.assertEqual(literal(None), "NULL")
        self.assertEqual(literal("Posto D'Água"), "'Posto D''Água'")

    def test_setup_contains_all_views_and_separates_namespaces(self):
        for schema in ["lab_m04", "gold"]:
            sql = setup(schema)
            self.assertEqual(sql.count("EXEC(N'CREATE OR ALTER VIEW"), 6)
            self.assertEqual(sql.count("EXEC(N'CREATE OR ALTER PROCEDURE"), 1)
            self.assertNotRegex(sql, r"(?m)^GO\s*$")
            self.assertNotIn("lab_m04.", sql if schema == "gold" else "")
            self.assertIn("@inject_fail_before_commit", sql)
            self.assertIn("ROLLBACK TRANSACTION", sql)
        self.assertIn("Gold oficial exige baseline", setup("gold"))

    def test_package_rebuild_is_deterministic_and_every_file_is_bound(self):
        temp_root = ROOT / "data/test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            output = Path(temp)
            first, digest1 = build_bundle(output)
            second, digest2 = build_bundle(output)
            self.assertEqual((first, digest1), (second, digest2))
            self.assertEqual(len(first["files"]), 5)
            self.assertEqual(first["source_table"], "silver_preco_publicado")
            self.assertEqual(first["delta_version_strategy"], "successful_m03_consumer_contract")
            for name, spec in first["files"].items():
                payload = (output / "upload" / name).read_bytes()
                self.assertEqual((len(payload), hashlib.sha256(payload).hexdigest()), (spec["bytes"], spec["sha256"]))
            for name, digest in first["warehouse_files"].items():
                self.assertEqual(hashlib.sha256((output / "warehouse" / name).read_bytes()).hexdigest(), digest)
            suite = (output / "warehouse/03_lab_fixture_suite.sql").read_text(encoding="utf-8")
            self.assertEqual(suite.count("INSERT INTO lab_m04.fixture_checks VALUES"), 7)
            self.assertIn("ERROR_NUMBER() <> 51006", suite)
            self.assertIn("ERROR_NUMBER() <> 51999", suite)
            self.assertNotIn("'None'", suite)
            loader = (output / "warehouse/30_import_approved_snapshot.sql").read_text(encoding="utf-8")
            self.assertIn("INSERT INTO gold.expected_posto", loader)
            self.assertIn("INSERT INTO gold.expected_weekly", loader)
            self.assertIn("QUOTENAME(@lakehouse)", loader)
            self.assertIn("@batch=@batch_id", loader)

    def test_generated_notebook_is_valid_and_bound_to_manifest(self):
        path = ROOT / "notebooks/07_export_gold_input.ipynb"
        notebook = nbformat.read(path, as_version=4)
        nbformat.validate(notebook)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                compile(cell.source, str(path), "exec")
        params = {}
        exec(notebook.cells[1].source, params)
        payload = (ROOT / "data/artifacts/m04_fabric/upload/manifest.json").read_bytes()
        self.assertEqual(params["p_expected_manifest_sha256"], hashlib.sha256(payload).hexdigest())
        source = (ROOT / "notebooks/m04_sources/07_export_gold_input.py").read_text(encoding="utf-8")
        self.assertEqual(notebook.cells[-1].source, source)
        module = ast.parse(source)
        writes = [node for node in ast.walk(module) if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Attribute) and node.func.attr == "saveAsTable"]
        self.assertEqual(len(writes), 2)
        self.assertIn('table = "m04_transfer_" + name', source)
        self.assertIn('saveAsTable("m04_transfer_manifest")', source)
        self.assertNotIn('.mode("overwrite")', source)
        self.assertIn('select_m03_contract(summaries, manifest, active_ids[0][0])', source)
        self.assertIn('compare_business(source, current)', source)
        self.assertIn('compare_business(parquet("reference.parquet"), source)', source)

    def receipt(self):
        manifest = json.loads((ROOT / "data/artifacts/m04_fabric/upload/manifest.json").read_text(encoding="utf-8"))
        snapshot = "b0f14322-3b2a-4ed0-864a-b54e05e71c48"
        contract = {"table": "silver_preco_publicado", "delta_version": 0, "scope_id": manifest["scope"]["scope_id"],
                    "source_sha256": manifest["source_sha256"], "ibge_sha256": manifest["ibge_sha256"],
                    "snapshot_id": snapshot, "business_fields": BUSINESS_FIELDS}
        receipt = {"status": "m03_official_selection_validated", "environment": "fabric", "official_integration_implemented": True,
                   "replay_without_active_commit": True, "m02_inputs_unchanged": True, "silver_rows": 8052, "stations": 502,
                   "municipalities": 27, "unusual_iqr_rows": 26, "consumer_contract": contract}
        return manifest, snapshot, receipt

    def test_m03_receipt_pins_active_snapshot_and_nonnegative_delta_version(self):
        manifest, snapshot, receipt = self.receipt()
        path, contract = select_m03_contract([("audit/summary.json", receipt)], manifest, snapshot)
        self.assertEqual(path, "audit/summary.json")
        self.assertEqual(contract["delta_version"], 0)
        self.assertEqual(contract["snapshot_id"], snapshot)

    def test_m03_receipt_rejects_failed_stale_incomplete_and_mismatched_sources(self):
        from copy import deepcopy
        manifest, snapshot, original = self.receipt()
        for field, value in [("status", "failed"), ("official_integration_implemented", False),
                             ("m02_inputs_unchanged", False), ("silver_rows", 8051)]:
            receipt = {**original, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                select_m03_contract([("bad.json", receipt)], manifest, snapshot)
        for field, value in [("table", "silver_preco_coletado"), ("source_sha256", "0"*64),
                             ("snapshot_id", "stale"), ("delta_version", -1), ("delta_version", True), ("delta_version", "0")]:
            receipt = deepcopy(original)
            receipt["consumer_contract"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                select_m03_contract([("bad.json", receipt)], manifest, snapshot)

    def test_receipt_selection_ignores_failed_runs_and_preserves_input(self):
        from copy import deepcopy
        manifest, snapshot, receipt = self.receipt()
        before = deepcopy(receipt)
        selected = select_m03_contract([("bad.json", {"status": "failed"}), ("good.json", receipt)], manifest, snapshot)
        self.assertEqual(selected[0], "good.json")
        self.assertEqual(receipt, before)


if __name__ == "__main__":
    unittest.main()
