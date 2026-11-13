"""Cria somente itens de laboratorio na capacidade trial; nao emite eventos."""
import base64
import json
import time
from datetime import datetime, timezone

from client import ROOT, request

config = json.loads((ROOT / '.local/fabric-environment.json').read_text())
workspace = config['workspace_id']
folder = ROOT / '.local/m10-api'
folder.mkdir(exist_ok=True)
binding = folder / 'binding.json'
state = json.loads(binding.read_text()) if binding.exists() else {}


def save():
    binding.write_text(json.dumps(state, indent=2))


def create(key, collection, payload):
    base = f'workspaces/{workspace}/{collection}'
    entry = state.setdefault(key, {})
    if not entry.get('id') and entry.get('location'):
        deadline = time.monotonic() + 600
        while True:
            operation = request('GET', entry['location']).json()
            entry['operation_status'] = operation['status']
            save()
            assert operation['status'] != 'Failed', operation.get('error')
            if operation['status'] == 'Succeeded':
                entry['id'] = request('GET', entry['location'].rstrip('/') + '/result').json()['id']
                save()
                break
            assert time.monotonic() < deadline, 'Retomar mesma operacao; nao recriar item'
            time.sleep(15)
    if not entry.get('id'):
        matches = [item for item in request('GET', base).json()['value'] if item['displayName'] == payload['displayName']]
        assert len(matches) <= 1
        if matches:
            entry['id'] = matches[0]['id']
        else:
            entry['requested_at_utc'] = datetime.now(timezone.utc).isoformat()
            save()
            response = request('POST', base, payload)
            entry['http_status'] = response.status_code
            entry['location'] = response.headers.get('Location')
            if response.status_code == 201:
                entry['id'] = response.json()['id']
            save()
            if response.status_code == 202:
                return create(key, collection, payload)
            assert response.status_code == 201
        save()
    actual = request('GET', base + '/' + entry['id']).json()
    (folder / (key + '-item.json')).write_text(json.dumps(actual, indent=2))
    print(key + ' ready (metadata only)', flush=True)
    return actual


ws = request('GET', f'workspaces/{workspace}').json()
capacity = next(c for c in request('GET', 'capacities').json()['value'] if c['id'] == ws['capacityId'])
assert capacity['state'] == 'Active' and capacity['sku'].startswith('FTL'), 'Apenas trial existente autorizado'
state['capacity_verified_at_utc'] = datetime.now(timezone.utc).isoformat()
state['capacity_sku'] = capacity['sku']
save()

eventhouse = create('eventhouse', 'eventhouses', {'displayName': 'eh_fuelwatch_lab',
    'description': 'M10 synthetic finite laboratory; no ANP data; minimum consumption disabled',
    'creationPayload': {'minimumConsumptionUnits': 0}})
assert eventhouse['properties'].get('minimumConsumptionUnits', 0) == 0
database = create('database', 'kqlDatabases', {'displayName': 'kql_fuelwatch_lab',
    'description': 'M10 synthetic events only',
    'creationPayload': {'databaseType': 'ReadWrite', 'parentEventhouseItemId': eventhouse['id']}})
assert database['properties']['parentEventhouseItemId'] == eventhouse['id']

topology = {'sources': [{'name': 'synthetic_endpoint', 'type': 'CustomEndpoint', 'properties': {}}],
            'destinations': [], 'operators': [],
            'streams': [{'name': 'synthetic_stream', 'type': 'DefaultStream', 'properties': {},
                         'inputNodes': [{'name': 'synthetic_endpoint'}]}], 'compatibilityLevel': '1.1'}
part = {'path': 'eventstream.json', 'payloadType': 'InlineBase64',
        'payload': base64.b64encode(json.dumps(topology).encode()).decode()}
eventstream = create('eventstream', 'eventstreams', {'displayName': 'es_fuelwatch_lab',
    'description': 'M10 synthetic custom endpoint; no emitter started', 'definition': {'parts': [part]}})
topology = request('GET', f"workspaces/{workspace}/eventstreams/{eventstream['id']}/topology").json()
(folder / 'topology-initial.json').write_text(json.dumps(topology, indent=2))
assert len(topology['sources']) == 1 and topology['sources'][0]['name'] == 'synthetic_endpoint'
state['source_id'] = topology['sources'][0]['id']
state['status'] = 'items_created_no_events_emitted'
save()
print('M10 items created on existing trial; no events emitted, no paid capacity', flush=True)
