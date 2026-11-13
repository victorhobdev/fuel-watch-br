"""Uma pagina PBIR com evolucao, comparacao municipal e cobertura."""
import base64
import json
import requests
import sys

from client import ROOT, definition_operation, request

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/m11-api'
binding = folder / 'binding.json'
s = json.loads(binding.read_text())
schema = 'https://developer.microsoft.com/json-schemas/fabric/item/report/'
page = 'fuelwatch_overview'
parts = {
    'definition.pbir': {'$schema': schema + 'definitionProperties/2.0.0/schema.json', 'version': '4.0',
        'datasetReference': {'byConnection': {'connectionString': 'semanticmodelid=' + s['semantic_model_id']}}},
    'definition/version.json': {'$schema': schema + 'definition/versionMetadata/1.0.0/schema.json', 'version': '2.0.0'},
    'definition/report.json': {'$schema': schema + 'definition/report/3.1.0/schema.json',
        'themeCollection': {'baseTheme': {'name': 'CY25SU12', 'reportVersionAtImport': {'visual': '2.5.0', 'report': '3.1.0', 'page': '2.3.0'}, 'type': 'SharedResources'}},
        'resourcePackages': [{'name': 'SharedResources', 'type': 'SharedResources', 'items': [{'name': 'CY25SU12', 'path': 'BaseThemes/CY25SU12.json', 'type': 'BaseTheme'}]}]},
    'definition/pages/pages.json': {'$schema': schema + 'definition/pagesMetadata/1.0.0/schema.json', 'pageOrder': [page], 'activePageName': page},
    f'definition/pages/{page}/page.json': {'$schema': schema + 'definition/page/2.0.0/schema.json', 'name': page,
        'displayName': 'Observatorio ANP', 'displayOption': 'FitToPage', 'height': 900, 'width': 1440}}


def field(name, measure=False):
    name = {'inicio_semana_iso': 'Semana', 'municipio_origem': 'Municipio'}.get(name, name)
    return {('Measure' if measure else 'Column'): {'Expression': {'SourceRef': {'Entity': 'Coletas'}}, 'Property': name}}


def projection(name, measure=False):
    label = {'inicio_semana_iso': 'Semana', 'municipio_origem': 'Municipio'}.get(name, name)
    return {'field': field(name, measure), 'queryRef': 'Coletas.' + label, 'nativeQueryRef': label}


def visual(name, kind, x, y, width, height, query, title):
    title_properties = {'show': {'expr': {'Literal': {'Value': 'true'}}},
                        'text': {'expr': {'Literal': {'Value': "'" + title.replace("'", "''") + "'"}}}}
    item = {'$schema': schema + 'definition/visualContainer/2.0.0/schema.json', 'name': name,
        'position': {'x': x, 'y': y, 'z': len(parts), 'height': height, 'width': width, 'tabOrder': len(parts)},
        'visual': {'visualType': kind, 'query': {'queryState': query}, 'drillFilterOtherVisuals': True,
            'visualContainerObjects': {'title': [{'properties': title_properties}]}}}
    parts[f'definition/pages/{page}/visuals/{name}/visual.json'] = item


for index, (name, title) in enumerate([('Coletas', 'Coletas de preco'), ('Postos observados', 'Postos observados'),
    ('Municipios observados', 'Municipios com coleta'), ('Preco medio', 'Preco medio por coleta — R$/litro')]):
    visual('kpi_' + str(index), 'card', 24 + index * 354, 70, 336, 120,
           {'Values': {'projections': [projection(name, True)]}}, title)
visual('weekly', 'lineChart', 24, 210, 820, 350, {'Category': {'projections': [projection('inicio_semana_iso')]},
    'Y': {'projections': [projection('Preco medio', True)]}}, 'Evolucao semanal — media das coletas, R$/litro')
visual('cities', 'barChart', 866, 210, 550, 650, {'Category': {'projections': [projection('municipio_origem')]},
    'Y': {'projections': [projection('Preco medio', True)]}}, 'Comparacao municipal — R$/litro')
visual('coverage', 'tableEx', 24, 580, 820, 280, {'Values': {'projections': [projection('municipio_origem'),
    projection('Coletas', True), projection('Postos observados', True), projection('Preco medio', True)]}},
    'Cobertura por municipio — observacoes da pesquisa')
header = {'$schema': schema + 'definition/visualContainer/2.0.0/schema.json', 'name': 'header',
    'position': {'x': 24, 'y': 8, 'z': 0, 'height': 54, 'width': 1392, 'tabOrder': 0},
    'visual': {'visualType': 'textbox', 'objects': {'general': [{'properties': {'paragraphs': [{'textRuns': [
        {'value': 'Fuel Watch BR | ANP • GASOLINA / RJ • jan–jun 2026 • BRL/litro', 'textStyle': {'fontSize': '20pt', 'fontFamily': 'Segoe UI Semibold'}}]}]}}]}}}
parts[f'definition/pages/{page}/visuals/header/visual.json'] = header
native = folder / 'report'
for path, obj in parts.items():
    target = native / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
payload = {'definition': {'parts': [{'path': path, 'payloadType': 'InlineBase64',
    'payload': base64.b64encode(json.dumps(obj, ensure_ascii=False).encode()).decode()} for path, obj in parts.items()]}}
if not s.get('report_id'):
    matches = [i for i in request('GET', f"workspaces/{c['workspace_id']}/reports").json()['value'] if i['displayName'] == 'Fuel Watch BR']
    if matches:
        s['report_id'] = matches[0]['id']
    else:
        try:
            created = definition_operation(f"workspaces/{c['workspace_id']}/reports", {'displayName': 'Fuel Watch BR', **payload})
        except requests.HTTPError as exc:
            (folder / 'report-error.private.json').write_text(exc.response.text)
            print(exc.response.text, flush=True)
            raise
        s['report_id'] = created['id']
    binding.write_text(json.dumps(s, indent=2))
if '--update' in sys.argv:
    base = f"workspaces/{c['workspace_id']}/reports/{s['report_id']}"
    before = definition_operation(base + '/getDefinition')
    (folder / 'report-before-labels.json').write_text(json.dumps(before, indent=2))
    definition_operation(base + '/updateDefinition', payload)
actual = definition_operation(f"workspaces/{c['workspace_id']}/reports/{s['report_id']}/getDefinition")
(folder / 'report-readback.json').write_text(json.dumps(actual, indent=2))
print('Report created/readback verified; rendering inspection pending', flush=True)
