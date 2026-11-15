"""Regressoes para a publicacao versionada e o ambiente de rebuild."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Phase2IntegrityTests(unittest.TestCase):
    def test_publish_procedure_fences_the_expected_predecessor_before_replace(self):
        sql = (ROOT / "sql/history/03_publish.sql").read_text(encoding="utf-8")
        guard = sql.index("@expected_previous_batch_id")
        replace = sql.index("DELETE FROM gold_hist.publication")
        self.assertLess(guard, replace)
        self.assertIn("THROW 51847", sql[guard:replace])
        self.assertIn("@current_publications<>1", sql[guard:replace])

    def test_integrated_pipeline_passes_the_predecessor_selected_at_start(self):
        pipeline = (ROOT / "tools/fabric/phase2_history_pipeline.py").read_text(encoding="utf-8")
        stage = (ROOT / "sql/history/04_stage_and_publish.sql").read_text(encoding="utf-8")
        self.assertIn("p_expected_previous_batch_id", pipeline)
        self.assertIn("@expected_previous_batch_id=@expected_previous_batch_id", stage)
        self.assertIn("publication_before[0]['batch_id']", pipeline)

    def test_rebuild_environment_includes_warehouse_identity(self):
        source = (ROOT / "tools/fabric/phase2_rebuild_notebooks.py").read_text(encoding="utf-8")
        consumer = (ROOT / "tools/fabric/phase2_history_warehouse.py").read_text(encoding="utf-8")
        self.assertIn("'warehouse_id':s['warehouse']['id']", source)
        self.assertIn("target['warehouse']['id']", consumer)


if __name__ == "__main__":
    unittest.main()
