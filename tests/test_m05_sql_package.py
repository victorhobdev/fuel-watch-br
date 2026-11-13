"""Conferencias locais do pacote SQL; somente Fabric pode validar o dialeto."""
import contextlib
import io
from pathlib import Path
import runpy
import unittest


class SqlPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with contextlib.redirect_stdout(io.StringIO()):
            cls.package = runpy.run_path("scripts/build_m05_sql.py")

    def test_guard_preserves_lineage_and_all_station_attributes(self):
        source = self.package["guard_source"]
        publication = source("publication")
        for field in ["batch_id", "scope_id", "source_sha256", "ibge_sha256", "silver_delta_version",
                      "is_synthetic", "published_at_utc", "rows_published", "source_table", "snapshot_id"]:
            self.assertIn(field, publication)
        station = source("dim_posto")
        for field in ["posto_sk", "cnpj", "revenda_observada", "bandeira_observada", "municipio_ibge", "uf",
                      "observado_desde", "observado_ate"]:
            self.assertIn(field, station)
        self.assertIn("CAST(source_sha256 AS varbinary(8000))", publication)
        self.assertEqual(source("published_business_bytes"), "gold.published_business_bytes")

    def test_failure_guard_compares_both_directions_and_checks_cardinality(self):
        text = Path("data/artifacts/m05/warehouse/90_assert_unchanged.sql").read_text()
        self.assertEqual(text.count("THROW 51603"), 6)
        self.assertEqual(text.count(" EXCEPT "), 12)
        self.assertEqual(text.count("COUNT_BIG(*)"), 12)
        self.assertIn("Baseline ausente", text)


if __name__ == "__main__":
    unittest.main()
