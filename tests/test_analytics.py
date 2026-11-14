import unittest
from decimal import Decimal
from fuelwatch.analytics import decimal_median,relative_difference,row_hash

class AnalyticsContractTests(unittest.TestCase):
 def test_exact_even_odd_medians(self):
  self.assertEqual(decimal_median(['6.100','6.101']),Decimal('6.100500'))
  self.assertEqual(decimal_median(['8.000','6.000','7.000']),Decimal('7.000000'))
  self.assertIsNone(decimal_median([]))
 def test_ineligible_and_zero_reference_have_no_percentage(self):
  self.assertIsNone(relative_difference('6','5',False))
  self.assertIsNone(relative_difference('6','0',True))
  self.assertEqual(relative_difference('6','5',True),Decimal('20.000000'))
 def test_ties_do_not_become_positive_deviations(self):
  self.assertEqual(relative_difference('6.000','6',True),Decimal('0.000000'))
 def test_fingerprint_preserves_text_zeroes_and_nullable_values(self):
  self.assertNotEqual(row_hash(['001',None],['str','decimal']),row_hash(['1',0],['str','decimal']))
  self.assertEqual(row_hash([Decimal('6.100')],['decimal']),row_hash([Decimal('6.100000')],['decimal']))
