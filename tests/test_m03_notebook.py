import ast
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from fuelwatch.m02_reference import HEADERS, RAW_COLUMNS
from fuelwatch.versioning_lab import SCOPE
from scripts.build_m03_bundle import ROOT, build_bundle, scenarios


class M03NotebookTests(unittest.TestCase):
    def setUp(self):
        source = (ROOT / "notebooks/m03_sources/05_source_versions_backfill.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        preflight = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "preflight")
        namespace = {"hashlib": hashlib, "csv": csv, "io": io, "HEADERS": HEADERS,
                     "RAW_COLUMNS": RAW_COLUMNS, "scope": SCOPE}
        exec(compile(ast.Module(body=[preflight], type_ignores=[]), "m03_preflight", "exec"), namespace)
        self.preflight = namespace["preflight"]
        self.plan = scenarios()

    def test_scenario_coverage_and_historical_values(self):
        self.assertEqual(len(self.plan), 17)
        self.assertEqual(Counter(s["expected_status"] for s in self.plan),
                         {"published": 7, "replayed": 1, "rejected": 8, "failed_before_promotion": 1})
        by_name = {s["name"]: s for s in self.plan}
        rows = by_name["correction_january"]["expected_active_rows"]
        self.assertEqual([r["preco_venda"] for r in rows if r["data_coleta"] == "2026-01-05"], ["6.350"])
        self.assertEqual(max(r["data_coleta"] for r in rows), "2026-06-30")
        self.assertIn("2026-01-08", [r["data_coleta"] for r in by_name["late_arrival"]["expected_active_rows"]])
        self.assertNotIn("2026-01-12", [r["data_coleta"] for r in by_name["removed_row"]["expected_active_rows"]])

    def test_failed_candidate_is_only_activated_on_retry(self):
        before, failure, retry = self.plan[-3:]
        self.assertEqual(failure["expected_active_rows"], before["expected_active_rows"])
        self.assertEqual(failure["expected_active_sha256"], before["expected_active_sha256"])
        self.assertNotEqual(failure["manifest"]["sha256"], failure["expected_active_sha256"])
        self.assertEqual(failure["csv_utf8"], retry["csv_utf8"])
        self.assertEqual(retry["expected_active_sha256"], retry["manifest"]["sha256"])
        self.assertEqual([r["preco_venda"] for r in retry["expected_active_rows"] if r["data_coleta"] == "2026-01-05"], ["6.400"])

    def test_actual_notebook_preflight_matches_fixture_guards(self):
        previous = None
        structural = {"partial": "incomplete_snapshot", "stale_base": "stale_selection",
                      "bad_hash": "hash_mismatch", "bad_layout": "layout_mismatch"}
        for step in self.plan:
            reason, rows = self.preflight(step["manifest"], step["csv_utf8"].encode("utf-8"), previous)
            self.assertEqual(reason, structural.get(step["name"]), step["name"])
            if reason is None:
                self.assertIsInstance(rows, list)
                self.assertTrue(all(set(row) == set(RAW_COLUMNS) for row in rows))
            previous = step["expected_active_sha256"]

    def test_wrong_field_count_is_rejected(self):
        manifest = dict(self.plan[0]["manifest"])
        payload = (";".join(HEADERS) + "\nonly;two\n").encode("utf-8-sig")
        manifest["sha256"] = hashlib.sha256(payload).hexdigest()
        reason, rows = self.preflight(manifest, payload, None)
        self.assertEqual(reason, "field_count_mismatch")
        self.assertIsNone(rows)

    def test_bundle_is_deterministic_and_binds_all_payloads(self):
        temp_root = ROOT / "data/test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp:
            output = Path(temp)
            first, sha1 = build_bundle(output)
            second, sha2 = build_bundle(output)
            self.assertEqual((first, sha1), (second, sha2))
            self.assertEqual(hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest(), sha1)
            for name, spec in first["files"].items():
                data = (output / name).read_bytes()
                self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), (spec["bytes"], spec["sha256"]))
            with zipfile.ZipFile(output / "fuelwatch_rules.zip") as archive:
                for name in archive.namelist():
                    self.assertEqual(archive.read(name), (ROOT / name).read_bytes())
            fixture = json.loads((output / "scenarios.json").read_text(encoding="utf-8"))
            self.assertTrue(fixture["is_synthetic"])
            self.assertEqual(len(fixture["scenarios"]), 17)


if __name__ == "__main__":
    unittest.main()
