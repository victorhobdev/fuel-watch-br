import ast
from copy import deepcopy
import hashlib
import io
import json
import unittest

from fuelwatch.publication import policy_identity, publication_decision, validate_publication_policy
from scripts.build_m03_official_notebook import ROOT, reviewed_policy


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.policy, _ = reviewed_policy()
        self.manifest = json.loads((ROOT / "data/artifacts/m02/manifest.json").read_text(encoding="utf-8"))
        self.zero = {"inserted": 0, "removed": 0, "updated": 0}

    def test_initial_registration_requires_reviewed_complete_delta(self):
        self.assertEqual(publication_decision(self.policy, None, {"inserted":8052,"removed":0,"updated":0}, False), "published")

    def test_same_identity_is_noop_only_for_equal_business(self):
        previous = policy_identity(self.policy)
        self.assertEqual(publication_decision(self.policy, previous, self.zero, True), "replayed")
        with self.assertRaisesRegex(ValueError, "negócio diferente"):
            publication_decision(self.policy, previous, self.zero, False)
        with self.assertRaises(ValueError):
            publication_decision(self.policy, previous, {**self.zero, "updated":1}, False)

    def test_stale_policy_cannot_overwrite_another_version(self):
        previous = {**policy_identity(self.policy), "source_sha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "anterior diferente"):
            publication_decision(self.policy, previous, self.zero, True)

    def test_unapproved_removal_is_blocked(self):
        policy = deepcopy(self.policy)
        policy["expected_previous_identity"] = {**policy_identity(policy), "source_sha256": "b" * 64}
        with self.assertRaisesRegex(ValueError, "delta revisado"):
            publication_decision(policy, policy["expected_previous_identity"], {"inserted":0,"removed":3,"updated":0}, False)

    def test_reviewed_source_change_supports_old_correction(self):
        previous = policy_identity(self.policy)
        policy = deepcopy(self.policy)
        policy.update({"source_sha256": "b" * 64, "expected_previous_identity": previous,
                       "approved_delta": {"inserted":0,"removed":0,"updated":1}})
        manifest = deepcopy(self.manifest)
        manifest["anp"]["sha256"] = "b" * 64
        validate_publication_policy(policy, manifest)
        self.assertEqual(publication_decision(policy, previous, policy["approved_delta"], False), "published")

    def test_same_anp_with_different_reference_needs_explicit_predecessor(self):
        previous = policy_identity(self.policy)
        policy = deepcopy(self.policy)
        policy["ibge_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "anterior diferente"):
            publication_decision(policy, previous, self.zero, True)

    def test_partial_synthetic_scope_hash_and_invalid_delta_are_refused(self):
        for change in [{"complete_snapshot":False}, {"is_synthetic":True}, {"source_sha256":"0"*64},
                       {"scope":{**self.policy["scope"],"scope_id":"unsafe'"}},
                       {"approved_delta":{**self.zero,"removed":-1}},
                       {"approved_delta":{**self.zero,"inserted":True}}, {"approved_delta":None}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_publication_policy({**self.policy, **change}, self.manifest)

    def test_notebook_stream_hash_preserves_original_bytes(self):
        source = (ROOT / "notebooks/m03_sources/06_official_source_selection.py").read_text(encoding="utf-8")
        function = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "stream_sha")
        namespace = {"hashlib": hashlib}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "official_stream_sha", "exec"), namespace)
        data = b"\xef\xbb\xbfraw;CSV\r\n" * 100000
        self.assertEqual(namespace["stream_sha"](io.BytesIO(data)), hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    unittest.main()
