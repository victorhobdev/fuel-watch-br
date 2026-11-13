"""Corrige somente referencias de ambiente no destino antes de executar."""
import base64
import json

from client import ROOT, definition_operation, request

folder = ROOT / '.local/m08-api'
dev = json.loads((ROOT / '.local/fabric-environment.json').read_text())
test = json.loads((folder / 'environment-test.json').read_text())
existing = request('GET', 'connections').json()['value']
matches = [x for x in existing if x['displayName'] == 'http_anp_publica_test']
assert len(matches) <= 1
if matches:
    http = matches[0]
else:
    http = request('POST', 'connections', {'connectivityType': 'ShareableCloud', 'displayName': 'http_anp_publica_test',
        'connectionDetails': {'type': 'HttpServer', 'creationMethod': 'HttpServer.Contents',
            'parameters': [{'dataType': 'Text', 'name': 'url', 'value': 'https://www.gov.br'}]},
        'privacyLevel': 'Public', 'credentialDetails': {'singleSignOnType': 'None', 'connectionEncryption': 'NotEncrypted',
            'skipTestConnection': False, 'credentials': {'credentialType': 'Anonymous'}}}).json()
(folder / 'http-test.json').write_text(json.dumps(http, indent=2))
source_http = next(x['id'] for x in existing if x['displayName'] == 'http_anp_publica fuelwatch')
for name in ['pl_anp_landing', 'pl_fuelwatch_master']:
    source = folder / 'target-definitions' / (name + '.json')
    definition = json.loads(source.read_text())
    for part in definition['definition']['parts']:
        if part['path'] != 'pipeline-content.json':
            continue
        text = base64.b64decode(part['payload']).decode()
        text = text.replace(dev['warehouse_server'], test['warehouse_server']).replace(source_http, http['id'])
        assert dev['warehouse_server'] not in text and source_http not in text
        part['payload'] = base64.b64encode(text.encode()).decode()
    items = request('GET', f"workspaces/{test['workspace_id']}/items").json()['value']
    item = next(i for i in items if i['displayName'] == name)
    base = f"workspaces/{test['workspace_id']}/dataPipelines/{item['id']}"
    definition_operation(base + '/updateDefinition', {'definition': definition['definition']})
    actual = definition_operation(base + '/getDefinition')
    (folder / (name + '-bound-test.json')).write_text(json.dumps(actual, indent=2))
    body = base64.b64decode(next(p for p in actual['definition']['parts'] if p['path'] == 'pipeline-content.json')['payload']).decode()
    assert dev['warehouse_server'] not in body and source_http not in body
    print(name + ': test endpoint/connection verified', flush=True)
definition = json.loads((folder / 'target-definitions/df_m06_ibge_lab.json').read_text())
for part in definition['definition']['parts']:
    if part['path'] == 'mashup.pq':
        text = base64.b64decode(part['payload']).decode().replace(dev['workspace_id'], test['workspace_id']).replace(dev['lakehouse_id'], test['lakehouse_id'])
        assert dev['workspace_id'] not in text and dev['lakehouse_id'] not in text
        part['payload'] = base64.b64encode(text.encode()).decode()
base = f"workspaces/{test['workspace_id']}/dataflows/{test['dataflow_m06_id']}"
definition_operation(base + '/updateDefinition', {'definition': definition['definition']})
actual = definition_operation(base + '/getDefinition')
(folder / 'dataflow-bound-test.json').write_text(json.dumps(actual, indent=2))
print('Dataflow M points to test; existing generic OAuth retained, execution still unverified', flush=True)
