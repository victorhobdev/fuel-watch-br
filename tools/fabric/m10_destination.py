"""Liga Eventstream somente ao KQL database sintetico; nenhum emissor e iniciado."""
import base64
import json
import time
from uuid import uuid4
import requests

from client import ROOT, definition_operation, request

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
s = json.loads((ROOT / '.local/m10-api/binding.json').read_text())
folder = ROOT / '.local/m10-api'
base = f"workspaces/{c['workspace_id']}/eventstreams/{s['eventstream']['id']}"
definition = definition_operation(base + '/getDefinition')
(folder / ('before-destination-' + str(uuid4()) + '.json')).write_text(json.dumps(definition, indent=2))
part = next(p for p in definition['definition']['parts'] if p['path'] == 'eventstream.json')
topology = json.loads(base64.b64decode(part['payload']))
matches = [d for d in topology['destinations'] if d['name'] == 'synthetic_eventhouse']
if not matches:
    topology['destinations'].append({'id': str(uuid4()), 'name': 'synthetic_eventhouse', 'type': 'Eventhouse',
        'properties': {'dataIngestionMode': 'ProcessedIngestion', 'workspaceId': c['workspace_id'],
            'itemId': s['database']['id'], 'databaseName': s['database']['id'], 'tableName': 'lab_preco_eventos',
            'inputSerialization': {'type': 'Json', 'properties': {'encoding': 'UTF8'}}},
        'inputNodes': [{'name': 'synthetic_stream'}]})
    part['payload'] = base64.b64encode(json.dumps(topology).encode()).decode()
    try:
        definition_operation(base + '/updateDefinition', {'definition': definition['definition']})
    except requests.HTTPError as exc:
        (folder / 'destination-update-error.private.json').write_text(exc.response.text)
        print('Destination update rejected:', exc.response.status_code, 'details saved privately', flush=True)
        raise
deadline = time.monotonic() + 600
while True:
    actual = request('GET', base + '/topology').json()
    (folder / 'topology-with-destination.json').write_text(json.dumps(actual, indent=2))
    destination = next(d for d in actual['destinations'] if d['name'] == 'synthetic_eventhouse')
    print('Eventhouse destination:', destination['status'], 'error:', destination.get('error'), flush=True)
    if destination['status'] == 'Running':
        assert destination['properties']['databaseName'] == s['database']['id']
        break
    assert destination['status'] not in {'Failed', 'Warning'}, 'Diagnosticar destino antes de emitir'
    assert time.monotonic() < deadline
    time.sleep(30)
connection = request('GET', base + '/sources/' + s['source_id'] + '/connection').json()
assert connection['type'] == 'CustomEndpoint' and connection['accessKeys']['primaryConnectionString']
# Contem chaves SAS: arquivo ignorado; nunca imprimir conteudo.
(folder / 'source-connection.private.json').write_text(json.dumps(connection, indent=2))
print('Destination Running; source credential saved privately; no events emitted', flush=True)
