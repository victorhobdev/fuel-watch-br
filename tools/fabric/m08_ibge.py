"""Executa a referencia IBGE promovida no destino e acompanha o mesmo job."""
import json
import time
import argparse
import base64

from client import ROOT, request, definition_operation

folder = ROOT / '.local/m08-api'
parser = argparse.ArgumentParser()
parser.add_argument('--notebook', choices=['03_ibge_reference', '04_bronze_to_silver'], default='03_ibge_reference')
args = parser.parse_args()
label = 'ibge' if args.notebook.startswith('03') else 'm02-silver'
c = json.loads((folder / 'environment-test.json').read_text())
items = request('GET', f"workspaces/{c['workspace_id']}/items").json()['value']
item = next(i for i in items if i['displayName'] == args.notebook)
if args.notebook == '04_bronze_to_silver':
    definition = definition_operation(f"workspaces/{c['workspace_id']}/notebooks/{item['id']}/getDefinition?format=ipynb")
    notebook = json.loads(base64.b64decode(next(p for p in definition['definition']['parts'] if p['path'].endswith('.ipynb'))['payload']))
    assert notebook['metadata']['dependencies']['lakehouse']['default_lakehouse'] == c['lakehouse_id']
    assert notebook['metadata']['dependencies']['lakehouse']['default_lakehouse_workspace_id'] == c['workspace_id']
base = f"workspaces/{c['workspace_id']}/items/{item['id']}/jobs"
saved = folder / (label + '-job-accepted.json')
if saved.exists():
    accepted = json.loads(saved.read_text())
else:
    response = request('POST', base + '/RunNotebook/instances', {})
    accepted = {'job_id': response.headers['Location'].rstrip('/').split('/')[-1],
                'retry_after': int(response.headers.get('Retry-After', '60'))}
    saved.write_text(json.dumps(accepted, indent=2))
    print('Test IBGE accepted:', accepted['job_id'], flush=True)
    time.sleep(accepted['retry_after'])
while True:
    job = request('GET', base + '/instances/' + accepted['job_id']).json()
    (folder / (label + '-job.json')).write_text(json.dumps(job, indent=2))
    print('Test IBGE:', job['status'], flush=True)
    if job['status'] in {'Completed', 'Failed', 'Cancelled'}:
        assert job['status'] == 'Completed', job.get('failureReason')
        break
    time.sleep(30)
