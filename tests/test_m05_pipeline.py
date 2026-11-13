"""Conferencias do grafo preparado; nao substituem execucao no Fabric."""
import unittest

from scripts.build_m05_pipeline import build, sql_expression


class PipelineGraphTests(unittest.TestCase):
    def test_official_flow_requires_success_of_every_previous_stage(self):
        items = {a["name"]: a for a in build()["properties"]["activities"]}
        chain = ["Capture_Baseline", "Copy_ANP", "Bronze", "Silver", "Export_Gold_Input",
                 "Import_Gold", "Publish_Gold", "Validate_Gold"]
        self.assertEqual(items[chain[0]]["dependsOn"], [])
        for previous, current in zip(chain, chain[1:]):
            self.assertEqual(items[current]["dependsOn"], [{"activity": previous, "dependencyConditions": ["Succeeded"]}])

    def test_failure_paths_verify_protection_and_preserve_failed_pipeline(self):
        items = {a["name"]: a for a in build()["properties"]["activities"]}
        for original, guard, terminal in [("Silver", "Guard_Silver_Failure", "Fail_Silver"),
                                           ("Publish_Gold", "Guard_Gold_Failure", "Fail_Gold")]:
            self.assertEqual(items[guard]["dependsOn"], [{"activity": original, "dependencyConditions": ["Failed"]}])
            self.assertEqual(items[terminal]["type"], "Fail")
            self.assertEqual(items[terminal]["dependsOn"][0]["activity"], guard)
        self.assertEqual(items["Import_Gold"]["policy"]["retry"], 3)
        for name in ["Bronze", "Silver", "Export_Gold_Input", "Publish_Gold"]:
            self.assertEqual(items[name]["policy"]["retry"], 0)

    def test_root_parameters_and_export_batch_are_explicit(self):
        pipeline = build()
        items = {a["name"]: a for a in pipeline["properties"]["activities"]}
        for name, phase in [("Bronze", "bronze"), ("Silver", "silver"), ("Export_Gold_Input", "export")]:
            params = items[name]["typeProperties"]["parameters"]
            self.assertEqual(params["p_phase"]["value"], phase)
            self.assertEqual(params["p_root_run_id"]["value"]["value"], "@pipeline().RunId")
            self.assertEqual(items[name]["typeProperties"]["notebookId"], "{{NOTEBOOK_08_ID}}")
            self.assertRegex(items[name]["typeProperties"]["sessionTag"], r"^[A-Za-z0-9_]+$")
        self.assertEqual(len({items[name]["typeProperties"]["sessionTag"] for name in ["Bronze", "Silver", "Export_Gold_Input"]}), 1)
        sql = items["Import_Gold"]["typeProperties"]["scripts"][0]["text"]["value"]
        self.assertIn("json(activity('Export_Gold_Input').output.result.exitValue).batch_id", sql)
        self.assertNotIn("COLAR_BATCH", sql)

    def test_sql_literal_quotes_are_escaped_in_pipeline_expression(self):
        result = sql_expression("SELECT 'ready', '{{ROOT_RUN_ID}}';\n")
        self.assertEqual(result, {"type": "Expression", "value": "@concat('SELECT ''ready'', ''',pipeline().RunId,''';\n')"})


if __name__ == "__main__":
    unittest.main()
