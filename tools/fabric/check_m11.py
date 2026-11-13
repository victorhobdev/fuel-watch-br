"""Confronta DAX e SQL por total, semana, municipio e filtro de periodo."""
import json
from datetime import datetime, timezone

from client import ROOT
from powerbi import request
from warehouse import connect

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
s = json.loads((ROOT / '.local/m11-api/binding.json').read_text())
endpoint = f"groups/{c['workspace_id']}/datasets/{s['semantic_model_id']}/executeQueries"
out = ROOT / 'evidence/fabric/consumption'
out.mkdir(exist_ok=True)
sql_values = 'COUNT_BIG(*) AS Coletas,COUNT(DISTINCT cnpj) AS Postos,COUNT(DISTINCT municipio_ibge) AS Municipios,SUM(preco_venda) AS Soma,CAST(SUM(preco_venda) AS float)/COUNT_BIG(*) AS PrecoMedio'
dax_values = '"Coletas",[Coletas],"Postos",[Postos observados],"Municipios",[Municipios observados],"Soma",[Soma precos],"PrecoMedio",[Preco medio]'
cases = [
    ('total', 'EVALUATE ROW(' + dax_values + ')', 'SELECT ' + sql_values + ' FROM gold.powerbi_coletas', None),
    ('weekly', 'EVALUATE SUMMARIZECOLUMNS(Coletas[Semana],' + dax_values + ')',
     'SELECT inicio_semana_iso AS Grupo,' + sql_values + ' FROM gold.powerbi_coletas GROUP BY inicio_semana_iso', 'Coletas[Semana]'),
    ('municipal', 'EVALUATE SUMMARIZECOLUMNS(Coletas[Municipio],' + dax_values + ')',
     'SELECT municipio_origem AS Grupo,' + sql_values + ' FROM gold.powerbi_coletas GROUP BY municipio_origem', 'Coletas[Municipio]'),
    ('january', 'EVALUATE CALCULATETABLE(ROW(' + dax_values + '),Coletas[data_coleta]>=DATE(2026,1,1),Coletas[data_coleta]<DATE(2026,2,1))',
     "SELECT " + sql_values + " FROM gold.powerbi_coletas WHERE data_coleta>='2026-01-01' AND data_coleta<'2026-02-01'", None)]
checks = []
with connect(c) as connection:
    for name, dax, sql, group in cases:
        payload = request('POST', endpoint, {'queries': [{'query': dax}], 'serializerSettings': {'includeNulls': True}})
        assert 'error' not in payload and 'error' not in payload['results'][0], payload
        actual = payload['results'][0]['tables'][0]['rows']
        cursor = connection.cursor().execute(sql)
        columns = [x[0] for x in cursor.description]
        expected = [dict(zip(columns, row)) for row in cursor.fetchall()]
        def key(value):
            return str(value)[:10] if name == 'weekly' else str(value)
        lookup = {key(row['Grupo']) if group else 'total': row for row in expected}
        assert len(actual) == len(lookup)
        for row in actual:
            reference = lookup[key(row[group]) if group else 'total']
            for measure in ['Coletas', 'Postos', 'Municipios']:
                assert row['[' + measure + ']'] == reference[measure], (name, measure)
            for measure in ['Soma', 'PrecoMedio']:
                assert abs(float(row['[' + measure + ']']) - float(reference[measure])) < 1e-8, (name, measure)
        (out / ('dax-' + name + '.json')).write_text(json.dumps(actual, indent=2) + '\n')
        checks.append({'case': name, 'groups': len(actual), 'measures_compared': 5, 'all_equal': True})
report = {'status': 'five_measures_reconciled', 'environment': 'fabric', 'checks': checks,
          'source': 'Gold DirectQuery collection grain', 'weighted_mean': 'SUM(preco_venda)/COUNTROWS(Coletas)',
          'approximate_float_tolerance': 1e-8, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
          'report_visual_review': 'separate_render_evidence', 'full_m11_accepted': False}
(out / 'measure-verification-2026-11-13.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
