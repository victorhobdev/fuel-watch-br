"""Concilia código dos notebooks oficiais históricos com definições versionadas."""
import base64
import hashlib
import json
from datetime import datetime, timezone

from client import ROOT, definition_operation, request
from evidence import write_json

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
state = json.loads((ROOT / '.local/phase2-history/binding.json').read_text())
base = f"workspaces/{c['workspace_id']}"
checks = []
for key, name in [('notebook_id', '11_historico_bronze_silver'),
                  ('publication_notebook_id', '12_historico_publicacao')]:
    item = state[key]
    sessions = request('GET', f'{base}/notebooks/{item}/livySessions').json()
    assert not sessions.get('continuationToken')
    assert all(s['state'] in {'Succeeded', 'Failed', 'Cancelled', 'Dead', 'Error', 'Success'}
               for s in sessions['value']), 'Notebook possui sessão ativa'
    desired = json.loads((ROOT / 'notebooks' / (name + '.ipynb')).read_text(encoding='utf8'))
    desired['metadata']['dependencies'] = {'lakehouse': {'default_lakehouse': c['lakehouse_id'],
        'default_lakehouse_name': 'lh_fuelwatch', 'default_lakehouse_workspace_id': c['workspace_id'],
        'known_lakehouses': [{'id': c['lakehouse_id']}]}}
    path = f'{base}/notebooks/{item}'
    def read():
        definition = definition_operation(path + '/getDefinition?format=ipynb')
        return json.loads(base64.b64decode(next(x for x in definition['definition']['parts']
                                               if x['path'].endswith('.ipynb'))['payload']))
    current = read()
    sources = lambda nb: [cell['source'] for cell in nb['cells']]
    changed = sources(current) != sources(desired)
    if changed:
        payload = base64.b64encode(json.dumps(desired, ensure_ascii=False).encode()).decode()
        definition_operation(path + '/updateDefinition', {'definition': {'format': 'ipynb',
            'parts': [{'path': 'notebook-content.ipynb', 'payloadType': 'InlineBase64', 'payload': payload}]}})
        current = read()
    assert sources(current) == sources(desired)
    assert current['metadata']['dependencies']['lakehouse']['default_lakehouse'] == c['lakehouse_id']
    digest = hashlib.sha256(json.dumps(sources(current), ensure_ascii=False).encode()).hexdigest()
    checks.append({'notebook': name, 'code_sha256': digest, 'updated': changed, 'lakehouse_binding_verified': True})
    print('Notebook conferido:', name, 'atualizado:', changed, flush=True)
write_json(ROOT / 'evidence/phase2/history/notebook-sync.json',
           {'status': 'official_notebook_definitions_reconciled', 'environment': 'fabric',
            'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'notebooks': checks})
