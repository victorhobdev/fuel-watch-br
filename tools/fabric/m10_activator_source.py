"""Sink-first: Activator recebe a origem gerada pelo Eventstream, sem regra ainda."""
import base64
import json
import time
from uuid import uuid4

from client import ROOT, definition_operation, request

folder = ROOT / '.local/m10-api'
binding = folder / 'binding.json'
s = json.loads(binding.read_text())
c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
w = c['workspace_id']
entry = s.setdefault('activator', {})
if not entry.get('id') and not entry.get('location'):
    matches = [x for x in request('GET', f'workspaces/{w}/reflexes').json()['value'] if x['displayName'] == 'act_fuelwatch_lab']
    assert len(matches) <= 1
    if matches:
        entry['id'] = matches[0]['id']
    else:
        response = request('POST', f'workspaces/{w}/reflexes', {'displayName': 'act_fuelwatch_lab',
            'description': 'M10 synthetic threshold test; internal audit only; no email or Teams'})
        entry['location'] = response.headers.get('Location')
        if response.status_code == 201:
            entry['id'] = response.json()['id']
        binding.write_text(json.dumps(s, indent=2))
if not entry.get('id'):
    deadline = time.monotonic() + 600
    while True:
        op = request('GET', entry['location']).json()
        assert op['status'] != 'Failed', op
        if op['status'] == 'Succeeded':
            entry['id'] = request('GET', entry['location'].rstrip('/') + '/result').json()['id']
            break
        assert time.monotonic() < deadline
        time.sleep(15)
binding.write_text(json.dumps(s, indent=2))
base = f"workspaces/{w}/eventstreams/{s['eventstream']['id']}"
definition = definition_operation(base + '/getDefinition')
(folder / 'before-activator-sink.json').write_text(json.dumps(definition, indent=2))
part = next(p for p in definition['definition']['parts'] if p['path'] == 'eventstream.json')
topology = json.loads(base64.b64decode(part['payload']))
if not any(d['name'] == 'synthetic_activator' for d in topology['destinations']):
    topology['destinations'].append({'id': str(uuid4()), 'name': 'synthetic_activator', 'type': 'Activator',
        'properties': {'workspaceId': w, 'itemId': entry['id'],
            'inputSerialization': {'type': 'Json', 'properties': {'encoding': 'UTF8'}}},
        'inputNodes': [{'name': 'synthetic_stream'}]})
    part['payload'] = base64.b64encode(json.dumps(topology).encode()).decode()
    definition_operation(base + '/updateDefinition', {'definition': definition['definition']})
deadline = time.monotonic() + 600
while True:
    actual = request('GET', base + '/topology').json()
    (folder / 'topology-activator.json').write_text(json.dumps(actual, indent=2))
    target = next(d for d in actual['destinations'] if d['name'] == 'synthetic_activator')
    print('Activator destination:', target['status'], flush=True)
    if target['status'] == 'Running':
        break
    assert target['status'] not in {'Failed', 'Warning'}, target.get('error')
    assert time.monotonic() < deadline
    time.sleep(30)
reflex = definition_operation(f"workspaces/{w}/reflexes/{entry['id']}/getDefinition")
(folder / 'activator-source-definition.json').write_text(json.dumps(reflex, indent=2))
entities = json.loads(base64.b64decode(next(p for p in reflex['definition']['parts'] if p['path'] == 'ReflexEntities.json')['payload']))
sources = [e for e in entities if e['type'] == 'eventstreamSource-v1']
events = [e for e in entities if e['type'] == 'timeSeriesView-v1' and e['payload']['definition']['type'] == 'Event']
assert len(sources) == len(events) == 1
assert sources[0]['payload']['metadata']['eventstreamArtifactId'] == s['eventstream']['id']
entry['source_event_entity_id'] = events[0]['uniqueIdentifier']
binding.write_text(json.dumps(s, indent=2))
print('Auto-created Activator source and SourceEvent verified; no rule/action enabled', flush=True)
