from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import pyarrow.parquet as pq

from fuelwatch.contract import classify_rows
from fuelwatch.m02_reference import HEADERS, RAW_COLUMNS, BUSINESS_FIELDS, decode_reference, iqr_fences, synthetic_rows
from fuelwatch.source import HEADERS as SOURCE_HEADERS, ROOT, source_record
from scripts.build_m02_bundle import build_bundle


class M02Tests(unittest.TestCase):
    def test_interchange_mapping_preserves_all_source_columns(self):
        self.assertEqual(HEADERS, SOURCE_HEADERS)
        self.assertEqual(len(RAW_COLUMNS), len(set(RAW_COLUMNS)))
        self.assertEqual(len(RAW_COLUMNS), 16)

    def test_approved_ibge_snapshot_and_tamper_detection(self):
        spec, content = source_record("ibge_municipios_rj")
        rows, lookup = decode_reference(content, spec["sha256"])
        self.assertEqual(len(rows), 92)
        self.assertEqual(len(lookup), 92)
        self.assertEqual(lookup[("RJ", "RIO DE JANEIRO")], ["3304557"])
        with self.assertRaisesRegex(ValueError, "Hash"):
            decode_reference(content + b"x", spec["sha256"])

    def test_synthetic_scenarios_match_shared_contract(self):
        scope = json.loads((ROOT / "config/slice.json").read_text(encoding="utf-8"))
        raw = [(i + 2, dict(zip(HEADERS, [r[c] for c in RAW_COLUMNS]))) for i, r in enumerate(synthetic_rows())]
        accepted, invalid, duplicates, conflicts = classify_rows(raw, {("RJ", "RIO DE JANEIRO"): ["3304557"]}, scope)
        self.assertEqual((len(accepted), len(invalid), len(duplicates), len(conflicts)), (9, 2, 1, 2))
        low, high = iqr_fences([r["preco_venda"] for r in accepted])
        self.assertEqual((low, high), (Decimal("6.100"), Decimal("6.100")))
        self.assertEqual(sum(not low <= r["preco_venda"] <= high for r in accepted), 1)
        self.assertTrue(all(r["reasons"] and r["raw"] for r in invalid))

    def test_bundle_is_deterministic_and_preserves_reference_types(self):
        test_root = ROOT / "data/test-tmp"
        test_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as temp:
            out = Path(temp).resolve()
            self.assertTrue(out.is_relative_to(test_root.resolve()))
            first, sha1 = build_bundle(out)
            second, sha2 = build_bundle(out)
            self.assertEqual(sha1, sha2)
            self.assertEqual(first, second)
            self.assertEqual(hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest(), sha1)
            for name, spec in first["files"].items():
                content = (out / name).read_bytes()
                self.assertEqual(len(content), spec["bytes"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), spec["sha256"])
            table = pq.read_table(out / "reference.parquet")
            self.assertEqual(table.num_rows, 8052)
            self.assertEqual(table.column_names, BUSINESS_FIELDS)
            self.assertEqual(str(table.schema.field("preco_venda").type), "decimal128(10, 3)")
            self.assertEqual(str(table.schema.field("data_coleta").type), "date32[day]")
            with zipfile.ZipFile(out / "fuelwatch_rules.zip") as archive:
                self.assertEqual(archive.read("fuelwatch/contract.py"), (ROOT / "fuelwatch/contract.py").read_bytes())
                self.assertEqual(archive.read("fuelwatch/silver_spark.py"), (ROOT / "fuelwatch/silver_spark.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
