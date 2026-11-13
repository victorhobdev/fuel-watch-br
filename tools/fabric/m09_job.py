"""Prepara/executa benchmark somente leitura; POST nunca repetido em erro de rede."""
import argparse
import base64
import json
import time
from datetime import datetime, timezone

from client import ROOT, definition_operation, request, environment_config

parser = argparse.ArgumentParser()
action = parser.add_mutually_exclusive_group(required=True)
action.add_argument('--prepare', action='store_true')
action.add_argument('--start', action='store_true')
action.add_argument('--watch')
parser.add_argument('--retry-terminal', action='store_true', help='Nova tentativa somente apos verificar falha terminal anterior')
args = parser.parse_args()
config = environment_config()
workspace = config['workspace_id']
alias = config.get('benchmark_workspace_alias', 'dev')
assert alias in {'dev', 'test'}
folder = ROOT / ('.local/m09-test-api' if alias == 'test' else '.local/m09-api')
folder.mkdir(exist_ok=True)
binding = folder / 'binding.json'

if args.prepare:
    notebook_name = '09_weekly_benchmark_test' if alias == 'test' else '09_weekly_benchmark'
    workspace_info = request('GET', f'workspaces/{workspace}').json()
    capacity = next(c for c in request('GET', 'capacities').json()['value'] if c['id'] == workspace_info['capacityId'])
    assert capacity['state'] == 'Active' and capacity['sku'].startswith('FTL'), 'Somente capacidade trial ativa autorizada'
    settings = request('GET', f'workspaces/{workspace}/spark/settings').json()
    items = request('GET', f'workspaces/{workspace}/items').json()['value']
    (folder / 'inventory.json').write_text(json.dumps({'workspace': workspace_info, 'capacity': capacity,
        'spark_settings': settings, 'items': items, 'captured_at_utc': datetime.now(timezone.utc).isoformat()}, indent=2))
    state = json.loads(binding.read_text()) if binding.exists() else {}
    if state.get('create_location') and not state.get('notebook_id'):
        deadline = time.monotonic() + 300
        while True:
            operation = request('GET', state['create_location']).json()
            assert operation['status'] != 'Failed', operation
            if operation['status'] == 'Succeeded':
                state['notebook_id'] = request('GET', state['create_location'].rstrip('/') + '/result').json()['id']
                break
            assert time.monotonic() < deadline, 'Continuar o mesmo Location; nao recriar item'
            time.sleep(10)
    if not state.get('notebook_id'):
        matches = [item for item in items if item['displayName'] == notebook_name]
        assert len(matches) <= 1
        if matches:
            state['notebook_id'] = matches[0]['id']
        else:
            response = request('POST', f'workspaces/{workspace}/notebooks', {'displayName': notebook_name,
                'description': 'M09 controlled read-only weekly benchmark; no official table writes'})
            state['create_location'] = response.headers.get('Location')
            if response.status_code == 201:
                state['notebook_id'] = response.json()['id']
            binding.write_text(json.dumps(state, indent=2))
            if response.status_code == 202:
                raise SystemExit('Criacao aceita. Retomar --prepare para acompanhar o mesmo Location.')
    binding.write_text(json.dumps(state, indent=2))
    notebook = json.loads((ROOT / 'notebooks/09_weekly_benchmark.ipynb').read_text(encoding='utf-8'))
    if config.get('benchmark_snapshot_id'):
        notebook['cells'][0]['source'] = ['p_snapshot_id = ' + json.dumps(config['benchmark_snapshot_id']) + '\n']
    notebook['metadata']['dependencies'] = {'lakehouse': {'default_lakehouse': config['lakehouse_id'],
        'default_lakehouse_name': 'lh_fuelwatch', 'default_lakehouse_workspace_id': workspace,
        'known_lakehouses': [{'id': config['lakehouse_id']}]}}
    expected = json.dumps(notebook, ensure_ascii=False).encode()
    body = {'definition': {'format': 'ipynb', 'parts': [{'path': 'notebook-content.ipynb',
        'payloadType': 'InlineBase64', 'payload': base64.b64encode(expected).decode()}]}}
    base = f"workspaces/{workspace}/notebooks/{state['notebook_id']}"
    definition_operation(base + '/updateDefinition', body)
    actual = definition_operation(base + '/getDefinition?format=ipynb')
    parts = actual['definition']['parts']
    content = next(part for part in parts if part['path'].endswith('.ipynb'))
    actual_nb = json.loads(base64.b64decode(content['payload']))
    assert [''.join(cell['source']) for cell in actual_nb['cells']] == [''.join(cell['source']) for cell in notebook['cells']]
    assert actual_nb['metadata']['dependencies']['lakehouse']['default_lakehouse'] == config['lakehouse_id']
    (folder / 'definition-readback.json').write_text(json.dumps(actual, indent=2))
    print('M09 preparado e relido; nenhum job iniciado', flush=True)
    raise SystemExit(0)

state = json.loads(binding.read_text())
base = f"workspaces/{workspace}/items/{state['notebook_id']}/jobs"
if args.start:
    existing = folder / 'accepted.json'
    if existing.exists():
        prior = json.loads(existing.read_text())
        assert args.retry_terminal, 'Job ja aceito: usar --watch; nova tentativa exige --retry-terminal'
        terminal = request('GET', base + '/instances/' + prior['job_id']).json()
        assert terminal['status'] == 'Failed', 'Somente falha terminal autoriza retry explicito'
        (folder / ('job-' + prior['job_id'] + '.json')).write_text(json.dumps(terminal, indent=2))
        (folder / ('accepted-' + prior['job_id'] + '.json')).write_text(json.dumps(prior, indent=2))
    items = request('GET', f'workspaces/{workspace}/items').json()['value']
    active = []
    for item in items:
        if item['type'] != 'Notebook':
            continue
        sessions = request('GET', f"workspaces/{workspace}/notebooks/{item['id']}/livySessions").json()['value']
        active.extend(s for s in sessions if s['state'] not in {'Succeeded', 'Failed', 'Cancelled', 'Dead', 'Error', 'Success'})
    assert not active, 'Sessao Spark ativa; acompanhar antes de iniciar benchmark'
    response = request('POST', base + '/RunNotebook/instances', {})
    job_id = response.headers['Location'].rstrip('/').split('/')[-1]
    accepted = {'job_id': job_id, 'location': response.headers['Location'],
        'accepted_at_utc': datetime.now(timezone.utc).isoformat(), 'retry_after': int(response.headers.get('Retry-After', '30'))}
    existing.write_text(json.dumps(accepted, indent=2))
    (folder / ('accepted-' + job_id + '.json')).write_text(json.dumps(accepted, indent=2))
    print(json.dumps(accepted), flush=True)
    time.sleep(accepted['retry_after'])
else:
    job_id = args.watch
while True:
    job = request('GET', base + '/instances/' + job_id).json()
    (folder / ('job-' + job_id + '.json')).write_text(json.dumps(job, indent=2))
    print(json.dumps({'job_id': job_id, 'status': job['status'], 'failure': job.get('failureReason')}), flush=True)
    if job['status'] in {'Completed', 'Failed', 'Cancelled', 'Deduped'}:
        break
    time.sleep(30)
