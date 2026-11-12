from copy import deepcopy
from datetime import date
from decimal import Decimal
import unittest

from fuelwatch.gold_local import calendar, load_input, open_model, publish_local, typed_fixture


class GoldTests(unittest.TestCase):
    def setUp(self):
        self.conn = open_model()
        self.addCleanup(self.conn.close)
        self.rows = typed_fixture()
        self.municipalities = [{"municipio_ibge": "3304557", "nome": "Rio de Janeiro", "uf": "RJ"}]

    def publish(self, rows=None):
        load_input(self.conn, self.rows if rows is None else rows, self.municipalities)
        publish_local(self.conn)

    def history(self):
        return self.conn.execute("SELECT * FROM lab_m04.dim_posto ORDER BY observado_desde").fetchall()

    def test_intervals_repetition_and_exact_boundary_assignment(self):
        self.publish()
        history = self.history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0][-2:], (date(2026, 1, 5), date(2026, 1, 19)))
        self.assertEqual(history[1][-2:], (date(2026, 1, 19), None))
        self.assertEqual(self.conn.execute("SELECT bandeira_observada FROM lab_m04.business_published WHERE data_coleta='2026-01-19'").fetchone()[0], "LAB B")
        self.publish()
        self.assertEqual(self.history(), history)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM lab_m04.fato_preco_coletado").fetchone()[0], 4)

    def test_late_attribute_observation_splits_history_and_reassigns_facts(self):
        self.publish()
        late = deepcopy(self.rows[1])
        late.update(data_coleta=date(2026, 1, 8), bandeira_observada="LAB C")
        self.publish(self.rows + [late])
        self.assertEqual([r[-2] for r in self.history()], [date(2026, 1, d) for d in [5, 8, 12, 19]])
        self.assertEqual(self.conn.execute("SELECT bandeira_observada FROM lab_m04.business_published WHERE data_coleta='2026-01-12'").fetchone()[0], "LAB SINTETICA")

    def test_attribute_correction_removes_obsolete_transition(self):
        self.publish()
        corrected = deepcopy(self.rows)
        for row in corrected[2:]:
            row.update(bandeira_observada=corrected[0]["bandeira_observada"], revenda_observada=corrected[0]["revenda_observada"])
        self.publish(corrected)
        self.assertEqual(len(self.history()), 1)
        self.assertIsNone(self.history()[0][-1])

    def test_price_only_correction_does_not_create_station_version(self):
        self.publish()
        before = self.history()
        self.rows[0]["preco_venda"] = Decimal("7.000")
        self.publish()
        self.assertEqual(self.history(), before)
        self.assertEqual(self.conn.execute("SELECT preco_venda FROM lab_m04.business_published ORDER BY data_coleta LIMIT 1").fetchone()[0], Decimal("7.000"))

    def test_observed_text_preserves_accent_case_and_trailing_space(self):
        self.rows[1]["revenda_observada"] = "Posto Observação "
        self.publish()
        value = self.conn.execute("SELECT revenda_observada FROM lab_m04.business_published WHERE data_coleta='2026-01-12'").fetchone()[0]
        self.assertEqual(value, "Posto Observação ")
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM (SELECT * FROM lab_m04.stage_business_bytes EXCEPT SELECT * FROM lab_m04.published_business_bytes)").fetchone()[0], 0)

    def test_rejected_input_preserves_published_fact_and_history(self):
        self.publish()
        before = self.history()
        for kind in ["duplicate", "missing_municipality", "conflicting_attributes"]:
            rows = deepcopy(self.rows)
            if kind == "missing_municipality":
                rows[0]["municipio_ibge"] = "9999999"
            else:
                extra = deepcopy(rows[0])
                if kind == "conflicting_attributes":
                    extra.update(unidade="m3", bandeira_observada="AMBIGUA")
                rows.append(extra)
            load_input(self.conn, rows, self.municipalities)
            with self.assertRaises(ValueError):
                publish_local(self.conn)
            self.assertEqual(self.history(), before)
            self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM lab_m04.fato_preco_coletado").fetchone()[0], 4)

    def test_iso_calendar_crosses_year_and_scope_boundary(self):
        result = calendar(date(2021, 1, 1), date(2021, 1, 4))
        self.assertEqual((result[0]["ano_iso"], result[0]["semana_iso"], result[0]["inicio_semana_iso"]), (2020, 53, date(2020, 12, 28)))
        self.assertEqual((result[-1]["ano_iso"], result[-1]["semana_iso"]), (2021, 1))
        self.assertEqual(calendar(date(2026, 1, 1), date(2026, 1, 1))[0]["inicio_semana_iso"], date(2025, 12, 29))

    def test_weekly_totals_reconcile_and_group_averages_need_weights(self):
        extra = deepcopy(self.rows[0])
        extra.update(cnpj="00000000000001", cnpj_origem="00.000.000/0000-01", preco_venda=Decimal("10.000"))
        self.publish(self.rows + [extra])
        count, total = self.conn.execute("SELECT SUM(coletas), SUM(soma_precos) FROM lab_m04.preco_semanal").fetchone()
        self.assertEqual((count, total), (5, Decimal("35.200")))
        weekly = self.conn.execute("SELECT preco_medio FROM lab_m04.preco_semanal").fetchall()
        self.assertNotAlmostEqual(sum(r[0] for r in weekly) / len(weekly), 35.2 / 5)


if __name__ == "__main__":
    unittest.main()
