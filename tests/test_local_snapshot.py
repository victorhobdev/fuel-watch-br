import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import pyarrow.parquet as pq

from fuelwatch.source import HEADERS
from scripts import prepare_local_slice as local
from tests.test_contract import sample_row


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parents[1] / "data/test-tmp"
        test_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=test_root)
        self.root = Path(self.temp.name).resolve()
        if not self.root.is_relative_to(test_root.resolve()):
            raise ValueError("Diretório de teste fora do workspace")
        self.addCleanup(self.temp.cleanup)
        (self.root / "config").mkdir()
        (self.root / "evidence").mkdir()
        self.scope = {"scope_id": "synthetic-fixture", "anp_source_id": "test-anp", "ibge_source_id": "test-ibge",
                      "uf": "RJ", "produto": "GASOLINA", "date_start": "2026-01-01", "date_end": "2026-06-30", "contract_version": "0.1"}
        (self.root / "config/slice.json").write_text(json.dumps(self.scope), encoding="utf-8")

    def run_rows(self, rows):
        content = io.StringIO(newline="")
        writer = csv.DictWriter(content, HEADERS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
        binary = io.BytesIO()
        with zipfile.ZipFile(binary, "w") as archive:
            archive.writestr("synthetic.csv", content.getvalue().encode("utf-8-sig"))
        anp = binary.getvalue()
        ibge = json.dumps([{"id": 3304557, "nome": "Rio de Janeiro", "regiao-imediata": {
            "regiao-intermediaria": {"UF": {"sigla": "RJ"}}}}]).encode()
        def source(key):
            payload = anp if key == "test-anp" else ibge
            return {"sha256": hashlib.sha256(payload).hexdigest(), "content_encoding": None}, payload
        with patch.object(local, "ROOT", self.root), patch.object(local, "source_record", source), contextlib.redirect_stdout(io.StringIO()):
            return local.prepare()

    def current(self):
        return json.loads((self.root / "data/local/synthetic-fixture/current.json").read_text())

    def test_repeat_then_old_correction_and_removed_row_replace_scope(self):
        first = sample_row()
        second = sample_row(**{"Data da Coleta": "06/01/2026"})
        initial = self.run_rows([first, second])
        repeat = self.run_rows([first, second])
        self.assertEqual(initial["business_sha256"], repeat["business_sha256"])
        self.assertTrue(repeat["same_business_state_as_previous"])
        corrected = self.run_rows([sample_row(**{"Valor de Venda": "6,25"})])
        self.assertNotEqual(initial["business_sha256"], corrected["business_sha256"])
        table = pq.read_table(self.root / self.current()["path"] / "observacoes.parquet")
        self.assertEqual(table.num_rows, 1)
        self.assertEqual(str(table.column("preco_venda")[0].as_py()), "6.250")
        self.assertTrue((self.root / initial["artifacts"] / "observacoes.parquet").exists())

    def test_conflicting_delivery_does_not_advance_current(self):
        self.run_rows([sample_row()])
        before = self.current()
        with self.assertRaisesRegex(ValueError, "Conflitos"):
            self.run_rows([sample_row(), sample_row(**{"Valor de Venda": "6,20"})])
        self.assertEqual(before, self.current())

    def test_write_failure_preserves_current_and_retry_does_not_duplicate(self):
        self.run_rows([sample_row()])
        before = self.current()
        with patch.object(local.pq, "write_table", side_effect=OSError("synthetic_write_failure")):
            with self.assertRaises(OSError):
                self.run_rows([sample_row(**{"Valor de Venda": "6,30"})])
        self.assertEqual(before, self.current())
        recovered = self.run_rows([sample_row(**{"Valor de Venda": "6,30"})])
        self.assertEqual(recovered["counts"]["accepted"], 1)

    def test_quarantine_and_outlier_do_not_share_rejection_rule(self):
        rows = [sample_row(**{"Data da Coleta": f"{day:02d}/01/2026"}) for day in range(1, 9)]
        rows += [sample_row(**{"Data da Coleta": "09/01/2026", "Valor de Venda": "99,90"}),
                 sample_row(**{"Data da Coleta": "10/01/2026", "Valor de Venda": "-1"})]
        report = self.run_rows(rows)
        self.assertEqual(report["counts"]["invalid"], 1)
        self.assertEqual(report["counts"]["accepted"], 9)
        self.assertEqual(report["unusual_iqr_rows"], 1)


if __name__ == "__main__":
    unittest.main()
