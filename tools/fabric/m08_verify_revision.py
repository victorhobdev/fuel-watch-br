"""Confere hash do codigo e Lakehouse do notebook promovido/restaurado."""
import argparse
import base64
import hashlib
import json
from client import ROOT, definition_operation

parser = argparse.ArgumentParser()
parser.add_argument('expected', choices=['before', 'after'])
args = parser.parse_args()
folder = ROOT / '.local/m08-api'
c = json.loads((folder / 'environment-test.json').read_text())
revision = json.loads((folder / '08-audit-revision.json').read_text())
actual = definition_operation(f"workspaces/{c['workspace_id']}/notebooks/{c['notebook_stage_id']}/getDefinition?format=ipynb")
notebook = json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path'].endswith('.ipynb'))['payload']))
assert notebook['metadata']['dependencies']['lakehouse']['default_lakehouse'] == c['lakehouse_id']
assert notebook['metadata']['dependencies']['lakehouse']['default_lakehouse_workspace_id'] == c['workspace_id']
source = ''.join(notebook['cells'][-1]['source'])
sha = hashlib.sha256(source.encode()).hexdigest()
assert sha == revision[args.expected + '_sha256']
(folder / ('08-test-' + args.expected + '-readback.json')).write_text(json.dumps(actual, indent=2))
(folder / ('08-test-' + args.expected + '-verified.json')).write_text(json.dumps({'source_sha256': sha,
    'expected_revision': args.expected, 'test_lakehouse_verified': True}, indent=2))
print('Test code hash matches ' + args.expected + ' revision; Lakehouse points to test', flush=True)
