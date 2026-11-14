"""Reconciliar medidas nacionais via DAX com consultas independentes no Warehouse."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from client import ROOT
from warehouse import connect, results
from powerbi import request
from evidence import write_json

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
s = json.loads((ROOT / '.local/phase2-bi/binding.json').read_text())
checks = []
with connect(c) as cn:
    cn.timeout = 600
    cases = [{'product':None}, {'product':'GASOLINA'}, {'product':'GNV'},
             {'product':'GASOLINA','uf':'RJ','brand':'BRANCA','week':'2026-06-22'},
             {'product':'GNV','uf':'RJ','week':'2026-06-22'}]
    for case in cases:
        product = case['product']
        filters = '' if product is None else ', TREATAS({"' + product + '"}, Produtos[Combustivel])'
        predicates = [] if product is None else ["produto='"+product+"'"]
        for param, table, column, source in [('uf','Estados','UF','uf'),('brand','Marcas','Bandeira','bandeira_observada')]:
            if param in case:
                filters += ', TREATAS({"'+case[param]+'"}, '+table+'['+column+'])'
                predicates.append(source+"='"+case[param]+"'")
        if 'week' in case:
            y,m,d=map(int,case['week'].split('-'))
            filters += f', TREATAS({{DATE({y},{m},{d})}}, Semanas[Semana])'
            predicates.append("data_coleta >= '"+case['week']+"' AND data_coleta < DATEADD(day,7,'"+case['week']+"')")
        dax = 'EVALUATE CALCULATETABLE(ROW("coletas", [Coletas], "postos", [Postos], "media", [Media por coleta])' + filters + ')'
        response = request('POST', f"groups/{c['workspace_id']}/datasets/{s['semantic_model_id']}/executeQueries", {
            'queries': [{'query': dax}], 'serializerSettings': {'includeNulls': True}})
        assert not response.get('error'), response
        result = response['results'][0]
        assert not result.get('error'), result
        row = result['tables'][0]['rows'][0]
        where = '' if not predicates else ' WHERE '+' AND '.join(predicates)
        expected = results(cn.cursor().execute(
            'SELECT COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos,AVG(CAST(preco_venda AS decimal(18,6))) AS media FROM gold_br.coletas' + where))[0][0]
        assert row['[coletas]'] == expected['coletas'], (row, expected)
        assert row['[postos]'] == expected['postos'], (row, expected)
        if product is None:
            assert row.get('[media]') is None, 'Preco misturou combustiveis/unidades'
        else:
            assert abs(Decimal(str(row['[media]'])) - Decimal(str(expected['media']))) < Decimal('0.000001'), (row, expected)
        checks.append({'filters': case, 'dax': dax, 'actual': row, 'warehouse': expected})
        print('DAX reconciled:', json.dumps(case), flush=True)
    metric_cases = [
        ('persistencia', 'EVALUATE CALCULATETABLE(ROW("value", [Persistencia acima], "contexts", [Semanas elegiveis]), TREATAS({"GASOLINA"}, Produtos[Combustivel]), TREATAS({"00002953000199"}, Precos[Posto]))',
         "SELECT persistencia_percentual/100.0 AS value,semanas_com_benchmark AS contexts FROM analise_br.persistencia_posto WHERE produto='GASOLINA' AND cnpj='00002953000199'"),
        ('bandeira_contextual', 'EVALUATE CALCULATETABLE(ROW("value", [Diferenca contextual bandeira], "contexts", [Contextos de bandeira]), TREATAS({"GASOLINA"}, Produtos[Combustivel]), TREATAS({"AC"}, Estados[UF]), TREATAS({"EQUADOR"}, Marcas[Bandeira]))',
         "SELECT diferenca_mediana_contextual AS value,contextos_comparaveis AS contexts FROM analise_br.comparacao_bandeira WHERE produto='GASOLINA' AND uf='AC' AND bandeira_observada='EQUADOR'")]
    for label,dax,sql in metric_cases:
        response=request('POST',f"groups/{c['workspace_id']}/datasets/{s['semantic_model_id']}/executeQueries",{'queries':[{'query':dax}],'serializerSettings':{'includeNulls':True}})
        assert 'error' not in response and 'error' not in response['results'][0],response
        row=response['results'][0]['tables'][0]['rows'][0]
        expected=results(cn.cursor().execute(sql))[0][0]
        assert row['[contexts]']==expected['contexts'],(label,row,expected)
        assert abs(Decimal(str(row['[value]']))-Decimal(str(expected['value'])))<Decimal('0.000001'),(label,row,expected)
        checks.append({'metric':label,'dax':dax,'actual':row,'warehouse':expected})
        print('DAX metric reconciled:',label,flush=True)
write_json(ROOT / 'evidence/phase2/analytics/model-check.json', {
    'status': 'national_model_dax_reconciled', 'environment': 'fabric',
    'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks})
