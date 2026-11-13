"""Prepara dois estagios na trial existente, sem executar cargas no destino."""
import json
import time

from client import ROOT, definition_operation, request

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/m08-api'
folder.mkdir(exist_ok=True)
path = folder / 'binding.json'
s = json.loads(path.read_text()) if path.exists() else {}
dev = request('GET', 'workspaces/' + c['workspace_id']).json()
capacity = next(x for x in request('GET', 'capacities').json()['value'] if x['id'] == dev['capacityId'])
assert capacity['state'] == 'Active' and capacity['sku'].startswith('FTL')
if not s.get('test_workspace_id'):
    matches = [x for x in request('GET', 'workspaces').json()['value'] if x['displayName'] == 'fuelwatch-test']
    assert len(matches) <= 1
    test = matches[0] if matches else definition_operation('workspaces', {'displayName': 'fuelwatch-test', 'description': 'Fuel Watch M08 deployment test; existing trial only'})
    s['test_workspace_id'] = test['id']
    path.write_text(json.dumps(s, indent=2))
test = request('GET', 'workspaces/' + s['test_workspace_id']).json()
if test.get('capacityId') != capacity['id']:
    response = request('POST', f"workspaces/{test['id']}/assignToCapacity", {'capacityId': capacity['id']})
    (folder / 'capacity-assignment.json').write_text(json.dumps({'status': response.status_code, 'location': response.headers.get('Location')}))
test = request('GET', 'workspaces/' + s['test_workspace_id']).json()
deadline = time.monotonic() + 300
while test.get('capacityId') != capacity['id'] or test.get('capacityAssignmentProgress') not in {None, 'Completed'}:
    assert time.monotonic() < deadline, 'Atribuicao pendente: consultar workspace, nao repetir POST'
    time.sleep(10)
    test = request('GET', 'workspaces/' + s['test_workspace_id']).json()
assert test['capacityId'] == capacity['id']
if not s.get('deployment_pipeline_id'):
    matches = [x for x in request('GET', 'deploymentPipelines').json()['value'] if x['displayName'] == 'dp_fuelwatch_dev_test']
    pipeline = matches[0] if matches else request('POST', 'deploymentPipelines', {
        'displayName': 'dp_fuelwatch_dev_test', 'description': 'Fuel Watch trial development to test',
        'stages': [{'displayName': 'Development', 'isPublic': False}, {'displayName': 'Test', 'isPublic': False}]}).json()
    s['deployment_pipeline_id'] = pipeline['id']
    path.write_text(json.dumps(s, indent=2))
base = 'deploymentPipelines/' + s['deployment_pipeline_id']
stages = request('GET', base + '/stages').json()['value']
for name, workspace in [('Development', c['workspace_id']), ('Test', s['test_workspace_id'])]:
    stage = next(x for x in stages if x['displayName'] == name)
    if stage.get('workspaceId') != workspace:
        assert not stage.get('workspaceId'), 'Estagio ocupado por outro workspace'
        request('POST', base + '/stages/' + stage['id'] + '/assignWorkspace', {'workspaceId': workspace})
    s[name.lower() + '_stage_id'] = stage['id']
    path.write_text(json.dumps(s, indent=2))
actual = request('GET', base + '/stages').json()
(folder / 'stages.json').write_text(json.dumps(actual, indent=2))
assert {x['workspaceId'] for x in actual['value']} == {c['workspace_id'], s['test_workspace_id']}
print('Dev/Test assigned to deployment pipeline; same active trial; no workload started', flush=True)
