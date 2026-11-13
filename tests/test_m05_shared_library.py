"""O compartilhamento nunca permite carregar uma biblioteca diferente da aprovada."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

SOURCE = Path("notebooks/m04_sources/bootstrap.py").read_text(encoding="utf-8")


class SharedLibraryTests(unittest.TestCase):
    def load(self, shared=None):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "m04_input"
            bundle.mkdir()
            payload = b"fixture zip; no Python code executed"
            (bundle / "fuelwatch_rules.zip").write_bytes(payload)
            manifest = json.dumps({"files": {"fuelwatch_rules.zip": {
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}}}).encode()
            (bundle / "manifest.json").write_bytes(manifest)
            shared_path = root / "m02_input/fuelwatch_rules.zip"
            if shared is not None:
                shared_path.parent.mkdir()
                shared_path.write_bytes(payload if shared else b"different library")
            calls = []
            values = {"p_bundle_dir": str(bundle), "p_rules_library_path": str(shared_path) if shared is not None else "",
                      "p_expected_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                      "spark": SimpleNamespace(sparkContext=SimpleNamespace(addPyFile=calls.append),
                                               conf=SimpleNamespace(set=lambda *args: None), version="fixture")}
            with contextlib.redirect_stdout(io.StringIO()):
                exec(SOURCE.replace('Path("/lakehouse/default/Files")', f"Path({str(root)!r})"), values)
            return calls[0], str(shared_path if shared is not None else bundle / "fuelwatch_rules.zip")

    def test_standalone_keeps_original_bundle_path(self):
        actual, expected = self.load()
        self.assertEqual(Path(actual), Path(expected))

    def test_shared_path_is_used_only_for_identical_approved_bytes(self):
        actual, expected = self.load(shared=True)
        self.assertEqual(Path(actual), Path(expected))

    def test_other_library_is_rejected_before_spark_registration(self):
        with self.assertRaisesRegex(ValueError, "Biblioteca compartilhada difere"):
            self.load(shared=False)
