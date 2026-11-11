import copy
from decimal import Decimal
import gzip
import json
import unittest

from fuelwatch.contract import classify_rows, validate_row
from fuelwatch.source import read_ibge, HEADERS

SCOPE = {"date_start": "2026-01-01", "date_end": "2026-06-30"}
LOOKUP = {("RJ", "RIO DE JANEIRO"): ["3304557"]}


def sample_row(**changes):
    # Fixture sintético: não representa um posto nem uma mudança de bandeira reais.
    raw = dict.fromkeys(HEADERS, "")
    raw.update({"Regiao - Sigla": "SE", "Estado - Sigla": "RJ", "Municipio": "RIO DE JANEIRO",
                "Revenda": "POSTO FICTICIO", "CNPJ da Revenda": " 00.000.000/0000-00",
                "Produto": "GASOLINA", "Data da Coleta": "05/01/2026", "Valor de Venda": "6,10",
                "Unidade de Medida": "R$ / litro", "Bandeira": "FICTICIA"})
    raw.update(changes)
    return raw


class ContractTests(unittest.TestCase):
    def test_decimal_and_leading_zero_cnpj_are_preserved(self):
        row, errors = validate_row(sample_row(), LOOKUP, SCOPE)
        self.assertFalse(errors)
        self.assertEqual(row["cnpj"], "00000000000000")
        self.assertEqual(row["preco_venda"], Decimal("6.100"))
        self.assertEqual(row["cnpj_origem"], " 00.000.000/0000-00")

    def test_invalid_values_are_quarantined_with_original(self):
        cases = [{"Valor de Venda": "0"}, {"Valor de Venda": "NaN"}, {"Valor de Venda": "6,1001"},
                 {"Data da Coleta": "31/02/2026"}, {"Data da Coleta": "31/12/2025"},
                 {"CNPJ da Revenda": "123"}, {"Unidade de Medida": "R$ / m³"}, {"Municipio": "INEXISTENTE"}]
        for change in cases:
            with self.subTest(change=change):
                raw = sample_row(**change)
                valid, invalid, duplicates, conflicts = classify_rows([(2, raw)], LOOKUP, SCOPE)
                self.assertEqual((len(valid), len(invalid), len(duplicates), len(conflicts)), (0, 1, 0, 0))
                self.assertEqual(invalid[0]["raw"], raw)
                self.assertTrue(invalid[0]["reasons"])

    def test_extreme_positive_price_is_not_invalid(self):
        row, errors = validate_row(sample_row(**{"Valor de Venda": "99,90"}), LOOKUP, SCOPE)
        self.assertFalse(errors)
        self.assertEqual(row["preco_venda"], Decimal("99.900"))

    def test_exact_duplicates_and_conflicts_are_distinct(self):
        first = sample_row()
        other = sample_row(**{"Valor de Venda": "6,20"})
        valid, invalid, duplicates, conflicts = classify_rows([(2, first), (3, copy.deepcopy(first)), (4, other)], LOOKUP, SCOPE)
        self.assertEqual((len(valid), len(invalid), len(duplicates), len(conflicts)), (0, 0, 1, 2))
        self.assertEqual({r["source_record"] for r in conflicts}, {2, 4})

    def test_ambiguous_municipality_is_not_arbitrarily_chosen(self):
        _, errors = validate_row(sample_row(), {("RJ", "RIO DE JANEIRO"): ["1", "2"]}, SCOPE)
        self.assertIn("municipio_ambiguo", errors)

    def test_ibge_compressed_and_plain_responses(self):
        payload = json.dumps([{"id": 3304557, "nome": "Rio de Janeiro"}]).encode()
        self.assertEqual(read_ibge(payload, None), read_ibge(gzip.compress(payload), "gzip"))


if __name__ == "__main__":
    unittest.main()
