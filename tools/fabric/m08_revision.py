"""Mudanca de auditoria reversivel para promover/restaurar sem alterar precos."""
import argparse
import base64
import hashlib
import json

from client import ROOT, definition_operation

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['prepare', 'rollback'])
args = parser.parse_args()
c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/m08-api'
backup = folder / '08-dev-before-audit-change.json'
base = f"workspaces/{c['workspace_id']}/notebooks/{c['notebook_stage_id']}"
current = definition_operation(base + '/getDefinition?format=ipynb')
part = next(p for p in current['definition']['parts'] if p['path'].endswith('.ipynb'))
notebook = json.loads(base64.b64decode(part['payload']))
marker = 'receipt["code_release"] = "m08_audit_v2"\n'
if args.action == 'prepare':
    assert not backup.exists(), 'Mudanca ja preparada: inspecionar antes de repetir'
    backup.write_text(json.dumps(current, indent=2))
    source = ''.join(notebook['cells'][-1]['source'])
    assert marker not in source and '\ndef save():' in source
    changed = source.replace('\ndef save():', marker + '\ndef save():', 1)
    compile(changed, '08-audit-v2', 'exec')
    notebook['cells'][-1]['source'] = changed.splitlines(keepends=True)
    (folder / '08-audit-revision.json').write_text(json.dumps({'before_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'after_sha256': hashlib.sha256(changed.encode()).hexdigest(), 'change': 'code_release in execution receipt only'}, indent=2))
else:
    assert marker in ''.join(notebook['cells'][-1]['source']), 'Nao sobrescrever codigo inesperado'
    old = json.loads(backup.read_text())
    old_nb = json.loads(base64.b64decode(next(p for p in old['definition']['parts'] if p['path'].endswith('.ipynb'))['payload']))
    notebook['cells'] = old_nb['cells']
part['payload'] = base64.b64encode(json.dumps(notebook, ensure_ascii=False).encode()).decode()
current['definition']['format'] = 'ipynb'
definition_operation(base + '/updateDefinition', {'definition': current['definition']})
actual = definition_operation(base + '/getDefinition?format=ipynb')
(folder / ('08-dev-' + args.action + '-readback.json')).write_text(json.dumps(actual, indent=2))
readback = json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path'].endswith('.ipynb'))['payload']))
assert ''.join(readback['cells'][-1]['source']) == ''.join(notebook['cells'][-1]['source'])
print('Dev revision ' + args.action + ' readback verified; no job executed', flush=True)
