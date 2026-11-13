"""Modelo enxuto DirectQuery sobre Gold; nao cria copia dos dados ANP."""
import base64
import json
import requests
import sys

from client import ROOT, definition_operation, request
from warehouse import connect, results

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/m11-api'
folder.mkdir(exist_ok=True)
binding = folder / 'binding.json'
s = json.loads(binding.read_text()) if binding.exists() else {}
with connect(c) as connection:
    exists = connection.cursor().execute("SELECT OBJECT_ID('gold.powerbi_coletas')").fetchone()[0]
    if exists is None:
        results(connection.cursor().execute('CREATE VIEW gold.powerbi_coletas AS SELECT b.*,d.inicio_semana_iso '
            'FROM gold.business_published b JOIN gold.dim_data d ON b.data_coleta=d.data'))
    check = results(connection.cursor().execute('SELECT COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos,'
        'COUNT(DISTINCT municipio_ibge) AS municipios,SUM(preco_venda) AS soma FROM gold.powerbi_coletas'))[0][0]
    assert (check['coletas'], check['postos'], check['municipios'], str(check['soma'])) == (8052, 502, 27, '52777.200')
fields = [('cnpj', 'string'), ('produto', 'string'), ('data_coleta', 'dateTime'), ('inicio_semana_iso', 'dateTime'),
          ('preco_venda', 'decimal'), ('moeda', 'string'), ('unidade', 'string'), ('uf', 'string'),
          ('municipio_ibge', 'string'), ('municipio_origem', 'string')]
measures = [
    {'name': 'Coletas', 'expression': 'COUNTROWS(Coletas)', 'formatString': '#,0'},
    {'name': 'Postos observados', 'expression': 'DISTINCTCOUNT(Coletas[cnpj])', 'formatString': '#,0'},
    {'name': 'Municipios observados', 'expression': 'DISTINCTCOUNT(Coletas[municipio_ibge])', 'formatString': '#,0'},
    {'name': 'Preco medio', 'expression': 'DIVIDE(CONVERT(SUM(Coletas[preco_venda]), DOUBLE), [Coletas])', 'formatString': 'R$ #,0.000'},
    {'name': 'Soma precos', 'expression': 'SUM(Coletas[preco_venda])', 'formatString': '#,0.000'}]
expression = ['let', f'    Source = Sql.Database("{c["warehouse_server"]}", "{c["warehouse_database"]}"),',
              '    Coletas = Source{[Schema="gold",Item="powerbi_coletas"]}[Data]', 'in', '    Coletas']
model = {'compatibilityLevel': 1604, 'model': {'culture': 'pt-BR', 'sourceQueryCulture': 'pt-BR',
    'defaultPowerBIDataSourceVersion': 'powerBI_V3', 'discourageImplicitMeasures': True,
        'tables': [{'name': 'Coletas', 'columns': [{'name': {'inicio_semana_iso': 'Semana', 'municipio_origem': 'Municipio'}.get(name, name), 'dataType': kind, 'sourceColumn': name,
        'summarizeBy': 'none', 'isHidden': name in {'cnpj', 'municipio_ibge'}} for name, kind in fields],
        'measures': measures, 'partitions': [{'name': 'Gold', 'mode': 'directQuery',
            'source': {'type': 'm', 'expression': expression}}]}]}}
parts = []
for name, obj in [('model.bim', model), ('definition.pbism', {'version': '5.0', 'settings': {'qnaEnabled': False}})]:
    parts.append({'path': name, 'payloadType': 'InlineBase64', 'payload': base64.b64encode(json.dumps(obj).encode()).decode()})
(folder / 'model-request.private.json').write_text(json.dumps({'definition': {'format': 'TMSL', 'parts': parts}}, indent=2))
if not s.get('semantic_model_id'):
    matches = [i for i in request('GET', f"workspaces/{c['workspace_id']}/semanticModels").json()['value'] if i['displayName'] == 'sm_fuelwatch']
    if matches:
        s['semantic_model_id'] = matches[0]['id']
    else:
        try:
            created = definition_operation(f"workspaces/{c['workspace_id']}/semanticModels", {'displayName': 'sm_fuelwatch',
                'description': 'ANP GASOLINA RJ Jan-Jun 2026; collection grain; BRL/litro; Gold DirectQuery',
                'definition': {'format': 'TMSL', 'parts': parts}})
        except requests.HTTPError as exc:
            (folder / 'model-error.private.json').write_text(exc.response.text)
            print(exc.response.text, flush=True)
            raise
        s['semantic_model_id'] = created['id']
    binding.write_text(json.dumps(s, indent=2))
if '--update' in sys.argv:
    base = f"workspaces/{c['workspace_id']}/semanticModels/{s['semantic_model_id']}"
    before = definition_operation(base + '/getDefinition?format=TMSL')
    (folder / 'model-before-labels.private.json').write_text(json.dumps(before, indent=2))
    definition_operation(base + '/updateDefinition', {'definition': {'format': 'TMSL', 'parts': parts}})
actual = definition_operation(f"workspaces/{c['workspace_id']}/semanticModels/{s['semantic_model_id']}/getDefinition?format=TMSL")
(folder / 'model-readback.private.json').write_text(json.dumps(actual, indent=2))
print('Semantic model created/read back; DAX execution and report validation pending', flush=True)
