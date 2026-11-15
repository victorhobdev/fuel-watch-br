"""Prepara arquivos e notebook de contexto; inicia ou acompanha um único job."""
import argparse
import base64
import hashlib
import json
import time
from datetime import datetime, timezone

from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT, credential, definition_operation, request
from evidence import write_json

p = argparse.ArgumentParser()
group = p.add_mutually_exclusive_group(required=True)
group.add_argument('--prepare', action='store_true')
group.add_argument('--start', action='store_true')
group.add_argument('--watch')
args = p.parse_args()
c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/phase2-context'
folder.mkdir(exist_ok=True)
binding = folder / 'binding.json'
state = json.loads(binding.read_text()) if binding.exists() else {}
base = f"workspaces/{c['workspace_id']}"
if args.prepare:
    workspace = request('GET', base).json()
    capacity = next(x for x in request('GET', 'capacities').json()['value'] if x['id'] == workspace['capacityId'])
    assert capacity['sku'].startswith('FTL') and capacity['state'] == 'Active', 'Usar somente capacidade trial ativa'
    fs = DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com', credential=credential).get_file_system_client(c['workspace_id'])
    for name in ['population', 'weather_municipal_weekly']:
        content = (ROOT / 'data/artifacts/context' / (name + '.parquet')).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        directory = c['lakehouse_id'] + '/Files/context/' + digest
        fs.get_directory_client(directory).create_directory()
        target = fs.get_file_client(directory + '/' + name + '.parquet')
        if not target.exists():
            target.create_file()
            target.append_data(content, offset=0, length=len(content))
            target.flush_data(len(content))
        assert hashlib.sha256(target.download_file().readall()).hexdigest() == digest
        print('Arquivo de contexto preservado:', name, digest, flush=True)
    nb = json.loads((ROOT / 'notebooks/15_context_references.ipynb').read_text(encoding='utf8'))
    nb['metadata']['dependencies'] = {'lakehouse': {'default_lakehouse': c['lakehouse_id'],
        'default_lakehouse_name': 'lh_fuelwatch', 'default_lakehouse_workspace_id': c['workspace_id'],
        'known_lakehouses': [{'id': c['lakehouse_id']}]}}
    definition = {'format': 'ipynb', 'parts': [{'path': 'notebook-content.ipynb', 'payloadType': 'InlineBase64',
        'payload': base64.b64encode(json.dumps(nb, ensure_ascii=False).encode()).decode()}]}
    matches = [x for x in request('GET', base + '/items').json()['value'] if x['displayName'] == '15_context_references']
    assert len(matches) <= 1
    if matches:
        state['notebook_id'] = matches[0]['id']
        definition_operation(base + '/notebooks/' + state['notebook_id'] + '/updateDefinition', {'definition': definition})
    else:
        item = definition_operation(base + '/notebooks', {'displayName': '15_context_references', 'definition': definition})
        state['notebook_id'] = item['id']
    write_json(binding, state)
    readback = definition_operation(base + '/notebooks/' + state['notebook_id'] + '/getDefinition?format=ipynb')
    actual = json.loads(base64.b64decode(next(x for x in readback['definition']['parts'] if x['path'].endswith('.ipynb'))['payload']))
    assert [x['source'] for x in actual['cells']] == [x['source'] for x in nb['cells']]
    print('Notebook preparado e conferido; execução ainda não iniciada', flush=True)
    raise SystemExit(0)
jobs = base + '/items/' + state['notebook_id'] + '/jobs'
if args.start:
    accepted = folder / 'accepted.json'
    pending = folder / 'pending.json'
    assert not accepted.exists() and not pending.exists(), 'Inspecionar tentativa anterior antes de repetir'
    for item in request('GET', base + '/items').json()['value']:
        if item['type'] == 'Notebook':
            sessions = request('GET', base + '/notebooks/' + item['id'] + '/livySessions').json()
            assert not sessions.get('continuationToken')
            assert all(s['state'] in {'Succeeded', 'Failed', 'Cancelled', 'Dead', 'Error', 'Success'} for s in sessions['value']), 'Sessão Spark ativa'
    write_json(pending, {'intent_at_utc': datetime.now(timezone.utc).isoformat()})
    response = request('POST', jobs + '/RunNotebook/instances', {'executionData': {'parameters': {}}})
    job = response.headers['Location'].rstrip('/').split('/')[-1]
    write_json(accepted, {'job_id': job, 'accepted_at_utc': datetime.now(timezone.utc).isoformat()})
    pending.unlink()
    print('Job aceito:', job, flush=True)
else:
    job = args.watch
while True:
    actual = request('GET', jobs + '/instances/' + job).json()
    write_json(folder / ('job-' + job + '.json'), actual)
    print(json.dumps({'job_id': job, 'status': actual['status'], 'failure': actual.get('failureReason')}), flush=True)
    if actual['status'] in {'Completed', 'Failed', 'Cancelled', 'Deduped'}:
        break
    time.sleep(20)
