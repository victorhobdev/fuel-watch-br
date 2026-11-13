import unittest

from kusto import rows


def response(status_code=0):
    return {'Tables': [
        {'TableName': 'Table_0', 'Columns': [{'ColumnName': 'Count'}], 'Rows': [[0]]},
        {'TableName': 'Table_1', 'Columns': [{'ColumnName': 'Severity'}, {'ColumnName': 'StatusCode'}],
         'Rows': [[4 if status_code == 0 else 2, status_code]]},
        {'TableName': 'Table_2', 'Columns': [{'ColumnName': name} for name in ['Ordinal', 'Kind', 'Name', 'Id', 'PrettyName']],
         'Rows': [[0, 'QueryResult', 'PrimaryResult', 'fixture', ''], [1, 'QueryStatus', 'QueryStatus', 'fixture', '']]}]}


class KustoResponseTests(unittest.TestCase):
    def test_v1_result_uses_toc_not_physical_table_name(self):
        self.assertEqual(rows(response()), [{'Count': 0}])

    def test_partial_result_with_http_success_is_not_accepted(self):
        with self.assertRaises(RuntimeError):
            rows(response(123))
