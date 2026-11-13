"""Promove somente o nucleo batch selecionado, sem executar pipeline no destino."""
import json
import argparse
from client import ROOT, definition_operation, request

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
parser = argparse.ArgumentParser()
parser.add_argument('--case', choices=['first', 'bootstrap04', 'audit_change', 'rollback'], default='first')
args = parser.parse_args()
folder = ROOT / '.local/m08-api'
s = json.loads((folder / 'binding.json').read_text())
items = request('GET', f"workspaces/{c['workspace_id']}/items").json()['value']
names = {'lh_fuelwatch', 'wh_fuelwatch', 'pl_anp_landing', 'pl_fuelwatch_master', '01_landing_to_bronze',
         '03_ibge_reference', '04_bronze_to_silver', '06_official_source_selection', '07_export_gold_input', '08_pipeline_stage', 'df_m06_ibge_lab'}
if args.case == 'bootstrap04':
    names = {'04_bronze_to_silver'}
elif args.case in {'audit_change', 'rollback'}:
    names = {'08_pipeline_stage'}
selected = [x for x in items if x['displayName'] in names and x['type'] != 'SQLEndpoint']
assert {x['displayName'] for x in selected} == names
body = {'sourceStageId': s['development_stage_id'], 'targetStageId': s['test_stage_id'],
        'items': [{'sourceItemId': x['id'], 'itemType': x['type']} for x in selected],
        'note': 'M08 first batch deployment from reviewed Fuel Watch version; runtime execution gated by bindings/data checks'}
record = folder / (args.case + '-deploy-request.json')
assert not record.exists(), 'Ja solicitado: inspecionar operacao salva antes de repetir'
record.write_text(json.dumps(body, indent=2))
try:
    result = definition_operation('deploymentPipelines/' + s['deployment_pipeline_id'] + '/deploy', body)
except Exception as exc:
    if getattr(exc, 'response', None) is not None:
        (folder / 'deploy-error.private.json').write_text(exc.response.text)
        print(exc.response.text, flush=True)
    raise
(folder / (args.case + '-deploy-result.json')).write_text(json.dumps(result, indent=2))
target = request('GET', f"workspaces/{s['test_workspace_id']}/items").json()
(folder / 'target-items.json').write_text(json.dumps(target, indent=2))
print('Deployment operation completed; target items:', [(x['displayName'], x['type']) for x in target['value']], flush=True)
