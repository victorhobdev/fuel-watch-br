"""Copia somente bundles imutaveis; nao copia tabelas/receipts para fingir execucao."""
import hashlib
import json
from datetime import datetime, timezone

from azure.storage.filedatalake import DataLakeServiceClient

from client import ROOT, credential, request
from warehouse import connect, results

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/m08-api'
s = json.loads((folder / 'binding.json').read_text())
target_items = request('GET', f"workspaces/{s['test_workspace_id']}/items").json()['value']
target_lh = next(i for i in target_items if i['displayName'] == 'lh_fuelwatch' and i['type'] == 'Lakehouse')
target_wh = next(i for i in target_items if i['displayName'] == 'wh_fuelwatch' and i['type'] == 'Warehouse')
wh = request('GET', f"workspaces/{s['test_workspace_id']}/warehouses/{target_wh['id']}").json()
config = {'workspace_id': s['test_workspace_id'], 'lakehouse_id': target_lh['id'],
          'warehouse_database': 'wh_fuelwatch', 'warehouse_server': wh['properties']['connectionInfo'],
          'pipeline_id': next(i['id'] for i in target_items if i['displayName'] == 'pl_fuelwatch_master'),
          'notebook_stage_id': next(i['id'] for i in target_items if i['displayName'] == '08_pipeline_stage'),
          'dataflow_m06_id': next(i['id'] for i in target_items if i['displayName'] == 'df_m06_ibge_lab')}
assert config['workspace_id'] != c['workspace_id'] and config['warehouse_server'] != c['warehouse_server']
(folder / 'environment-test.json').write_text(json.dumps(config, indent=2))
service = DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com', credential=credential)
origin = service.get_file_system_client(c['workspace_id'])
target = service.get_file_system_client(config['workspace_id'])
copied = []
for bundle in ['m02_input', 'm04_input']:
    prefix = c['lakehouse_id'] + '/Files/' + bundle
    for path in origin.get_paths(path=prefix):
        if path.is_directory:
            continue
        relative = path.name.split('/Files/', 1)[1]
        destination = config['lakehouse_id'] + '/Files/' + relative
        payload = origin.get_file_client(path.name).download_file().readall()
        client = target.get_file_client(destination)
        if not client.exists():
            target.get_directory_client(destination.rsplit('/', 1)[0]).create_directory()
            client.create_file()
            client.append_data(payload, offset=0, length=len(payload))
            client.flush_data(len(payload))
        actual = client.download_file().readall()
        assert actual == payload, 'Bundle existente diverge; nunca sobrescrever silenciosamente'
        copied.append({'path': relative, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
        print('Verified immutable input:', relative, flush=True)
with connect(config) as connection:
    current = results(connection.cursor().execute('SELECT COUNT_BIG(*) AS facts FROM gold.business_published; SELECT COUNT_BIG(*) AS attempts FROM m05.attempt;'))
(folder / 'target-sql-before.json').write_text(json.dumps(current, default=str, indent=2))
settings = request('GET', f"workspaces/{config['workspace_id']}/spark/settings").json()
if settings['environment']['runtimeVersion'] != '2.0' or not settings['highConcurrency']['notebookPipelineRunEnabled']:
    request('PATCH', f"workspaces/{config['workspace_id']}/spark/settings", {'environment': {'runtimeVersion': '2.0'},
        'highConcurrency': {'notebookPipelineRunEnabled': True}})
report = {'status': 'immutable_inputs_copied', 'environment': 'fabric_test', 'files': copied,
          'tables_or_execution_receipts_copied': False, 'checked_at_utc': datetime.now(timezone.utc).isoformat()}
(folder / 'inputs.json').write_text(json.dumps(report, indent=2))
print('Test inputs and SQL context verified; no workload started', flush=True)
