from copy import deepcopy
import unittest

from fuelwatch.versioning_lab import SCOPE, apply_delivery, delivery, prepare_cases


class VersioningTests(unittest.TestCase):
    def setUp(self):
        self.cases = prepare_cases()
        self.state = {"active": {"lab_m03_protected_scope": {"rows": [{"marker": "unchanged"}]}}, "versions": {}}
        self.scope = deepcopy(SCOPE)
        self.base_manifest, self.base_bytes = delivery(self.scope, self.cases["base"], None, {"inserted": 4, "removed": 0, "updated": 0})
        self.state, self.base_audit = apply_delivery(self.state, self.scope, self.base_manifest, self.base_bytes, "initial")

    def active(self, state=None):
        return (state or self.state)["active"][self.scope["scope_id"]]

    def candidate(self, case, expected):
        return delivery(self.scope, self.cases[case], self.active()["source_sha256"], expected)

    def test_same_delivery_keeps_business_and_pointer(self):
        state, audit = apply_delivery(self.state, self.scope, self.base_manifest, self.base_bytes, "repeat")
        self.assertEqual(audit["status"], "replayed")
        self.assertEqual(state["active"], self.state["active"])
        self.assertEqual(audit["business_sha256"], self.active()["business_sha256"])

    def test_old_correction_changes_only_january(self):
        manifest, payload = self.candidate("correction_january", {"inserted": 0, "removed": 0, "updated": 1})
        state, audit = apply_delivery(self.state, self.scope, manifest, payload, "correct")
        self.assertEqual(audit["status"], "published_in_local_model")
        self.assertEqual(len(audit["delta"]["updated"]), 1)
        self.assertEqual(audit["delta"]["updated"][0][2], "2026-01-05")
        self.assertEqual(audit["delta"]["unchanged"], 3)
        self.assertEqual(max(r["data_coleta"] for r in self.active(state)["rows"]), "2026-06-30")
        self.assertEqual(state["active"]["lab_m03_protected_scope"], self.state["active"]["lab_m03_protected_scope"])

    def test_late_addition_then_explicit_removal(self):
        for case, expected in [("correction_january", {"inserted": 0, "removed": 0, "updated": 1}),
                               ("late_arrival", {"inserted": 1, "removed": 0, "updated": 0}),
                               ("removed_row", {"inserted": 0, "removed": 1, "updated": 0})]:
            manifest, payload = self.candidate(case, expected)
            self.state, audit = apply_delivery(self.state, self.scope, manifest, payload, case)
            self.assertEqual(audit["status"], "published_in_local_model")
        dates = {r["data_coleta"] for r in self.active()["rows"]}
        self.assertIn("2026-01-08", dates)
        self.assertNotIn("2026-01-12", dates)
        self.assertEqual(len(self.active()["rows"]), 4)

    def test_exact_duplicate_does_not_add_an_observation(self):
        rows = self.cases["base"] + [deepcopy(self.cases["base"][0])]
        manifest, payload = delivery(self.scope, rows, self.active()["source_sha256"], {"inserted": 0, "removed": 0, "updated": 0})
        state, audit = apply_delivery(self.state, self.scope, manifest, payload, "duplicate")
        self.assertEqual(audit["status"], "published_in_local_model")
        self.assertEqual(audit["counts"]["exact_duplicate_excess"], 1)
        self.assertEqual(self.active(state)["business_sha256"], self.active()["business_sha256"])
        self.assertNotEqual(self.active(state)["source_sha256"], self.active()["source_sha256"])

    def test_conflicts_and_invalid_rows_preserve_active(self):
        for case in ["conflict", "invalid", "empty"]:
            with self.subTest(case=case):
                manifest, payload = self.candidate(case, None)
                state, audit = apply_delivery(self.state, self.scope, manifest, payload, case)
                self.assertEqual(audit["status"], "rejected")
                self.assertEqual(state["active"], self.state["active"])

    def test_partial_or_unapproved_removal_is_blocked(self):
        for complete in [False, True]:
            manifest, payload = delivery(self.scope, self.cases["base"][:1], self.active()["source_sha256"], None, complete)
            state, audit = apply_delivery(self.state, self.scope, manifest, payload, "partial")
            self.assertEqual(audit["reason"], "change_not_approved" if complete else "incomplete_snapshot")
            self.assertEqual(state["active"], self.state["active"])

    def test_stale_selection_cannot_regress_active(self):
        manifest, payload = self.candidate("correction_january", {"inserted": 0, "removed": 0, "updated": 1})
        state, _ = apply_delivery(self.state, self.scope, manifest, payload, "correct")
        again, audit = apply_delivery(state, self.scope, self.base_manifest, self.base_bytes, "stale")
        self.assertEqual(audit["reason"], "stale_selection")
        self.assertEqual(again["active"], state["active"])

    def test_hash_layout_and_scope_are_validated(self):
        for kind in ["hash", "layout", "scope"]:
            manifest, payload = self.candidate("base", {"inserted": 0, "removed": 0, "updated": 0})
            if kind == "hash":
                manifest["sha256"] = "0" * 64
            elif kind == "layout":
                payload = b"wrong;header\n1;2\n"
                import hashlib
                manifest["sha256"] = hashlib.sha256(payload).hexdigest()
            else:
                manifest["scope"]["uf"] = "SP"
            state, audit = apply_delivery(self.state, self.scope, manifest, payload, kind)
            self.assertEqual(audit["status"], "rejected")
            self.assertEqual(state["active"], self.state["active"])

    def test_official_scope_is_refused_and_inputs_are_not_mutated(self):
        before = deepcopy(self.state)
        scope = {**self.scope, "scope_id": "anp-2026-1-rj-gasolina"}
        with self.assertRaisesRegex(ValueError, "sintéticos"):
            apply_delivery(self.state, scope, self.base_manifest, self.base_bytes, "unsafe")
        self.assertEqual(self.state, before)


if __name__ == "__main__":
    unittest.main()
