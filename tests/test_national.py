import json,unittest
from pathlib import Path
from fuelwatch.national import SCOPE,national_reference
from fuelwatch.contract import validate_row

class NationalTests(unittest.TestCase):
 def row(self,product='GNV',unit='R$ / m³'):
  return {'CNPJ da Revenda':'01.234.567/0001-89','Revenda':'Posto','Bandeira':'BRANCA','Municipio':'Cidade','Produto':product,'Estado - Sigla':'SP','Data da Coleta':'01/01/2026','Valor de Venda':'4,100','Unidade de Medida':unit}
 def test_gnv_is_cubic_metre_and_cnpj_stays_text(self):
  row,reasons=validate_row(self.row(),{('SP','CIDADE'):['3550308']},SCOPE)
  self.assertFalse(reasons);self.assertEqual(row['unidade'],'m3');self.assertEqual(row['cnpj'],'01234567000189')
 def test_litre_does_not_validate_as_gnv(self):
  _,reasons=validate_row(self.row(unit='R$ / litro'),{('SP','CIDADE'):['3550308']},SCOPE)
  self.assertIn('unidade_incompativel_com_produto',reasons)
 def test_ascii_cubic_metre_requires_explicit_versioned_alias(self):
  raw=self.row(unit='R$ / m3');lookup={('SP','CIDADE'):['3550308']}
  _,reasons=validate_row(raw,lookup,SCOPE)
  self.assertIn('unidade_incompativel_com_produto',reasons)
  scoped={**SCOPE,'unit_aliases':{'R$ / m3':'R$ / m³'}}
  typed,reasons=validate_row(raw,lookup,scoped)
  self.assertFalse(reasons);self.assertEqual(typed['unidade'],'m3')
  self.assertEqual(raw['Unidade de Medida'],'R$ / m3')
  _,reasons=validate_row(self.row(unit='R$ / litro'),lookup,scoped)
  self.assertIn('unidade_incompativel_com_produto',reasons)
 def test_unknown_product_does_not_silently_enter(self):
  _,reasons=validate_row(self.row(product='NOVO'),{('SP','CIDADE'):['3550308']},SCOPE)
  self.assertIn('produto_fora_do_contrato',reasons)
 def test_all_known_liquids_are_accepted(self):
  for product in SCOPE['product_units']:
   unit=SCOPE['product_units'][product];row,reasons=validate_row(self.row(product,unit),{('SP','CIDADE'):['3550308']},SCOPE)
   self.assertFalse(reasons,product)
 def test_observed_alias_is_checked_against_official_code(self):
  items=[{'id':4317103,'nome':"Sant'Ana do Livramento"}];states=[{'id':43,'sigla':'RS'}]
  _,lookup=national_reference(items,states);self.assertEqual(lookup[('RS','SANTANA DO LIVRAMENTO')],['4317103'])
  with self.assertRaises(ValueError):national_reference([{'id':4317103,'nome':'Outra cidade'}],states)
