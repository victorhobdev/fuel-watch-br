"""Uma interrupcao da observacao nunca autoriza duplicar um job aceito."""
import ast
from pathlib import Path
import unittest

tree = ast.parse(Path("tools/fabric/m05_recovery_cases.py").read_text(encoding="utf-8"))
function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "resume_action")
scope = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), "resume_action", "exec"), scope)
resume_action = scope["resume_action"]


class ResumeTests(unittest.TestCase):
    def test_known_job_is_observed_again_after_monitoring_interruption(self):
        for status in ["accepted", "NotStarted", "InProgress", "Completed"]:
            self.assertEqual(resume_action("none", {"status": status, "job_id": "existing"}), "watch")

    def test_expected_failed_job_is_verified_instead_of_executed_again(self):
        for fault in ["silver", "gold"]:
            self.assertEqual(resume_action(fault, {"status": "Failed", "job_id": "existing"}), "watch")

    def test_terminal_failed_recovery_can_start_new_attempt(self):
        self.assertEqual(resume_action("none", {"status": "Failed", "job_id": "failed"}), "start")
        self.assertEqual(resume_action("none", None), "start")

    def test_verified_case_is_preserved(self):
        self.assertEqual(resume_action("silver", {"status": "verified", "job_id": "accepted"}), "skip")

    def test_uncertain_submission_and_cancel_require_inspection(self):
        for previous in [{"status": "starting"}, {"status": "Cancelled", "job_id": "cancelled"}]:
            with self.assertRaises(RuntimeError):
                resume_action("none", previous)
