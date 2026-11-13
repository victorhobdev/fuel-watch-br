"""Inventario somente leitura dos recursos do projeto, sem credenciais no relatorio."""
import json
from datetime import datetime, timezone
from client import ROOT, request

TERMINAL_JOBS = {'Completed', 'Failed', 'Cancelled', 'Deduped'}
TERMINAL_SESSIONS = {'Succeeded', 'Failed', 'Cancelled', 'Dead', 'Error', 'Success'}

def values(path):
    result = []
    while path:
        page = request('GET', path).json()
        result.extend(page.get('value', []))
        path = page.get('continuationUri')
        assert path or not page.get('continuationToken'), 'Paginacao exige URI antes de concluir inventario'
    return result

report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'workspaces': [],
          'trial_expiration_verified': False, 'cost_or_cu_measured': False}
capacities = values('capacities')
for alias, file in [('dev', '.local/fabric-environment.json'), ('test', '.local/m08-api/environment-test.json')]:
    c = json.loads((ROOT / file).read_text())
    ws = c['workspace_id']
    info = request('GET', 'workspaces/' + ws).json()
    cap = next(x for x in capacities if x['id'] == info['capacityId'])
    items = values(f'workspaces/{ws}/items')
    row = {'alias': alias, 'capacity_sku': cap['sku'], 'capacity_state': cap['state'],
           'active_jobs': [], 'active_spark_sessions': [], 'enabled_pipeline_schedules': [],
           'item_types': {kind: sum(x['type'] == kind for x in items) for kind in sorted({x['type'] for x in items})}}
    for item in items:
        if item['type'] in {'DataPipeline', 'Notebook', 'Dataflow'}:
            jobs = values(f"workspaces/{ws}/items/{item['id']}/jobs/instances")
            row['active_jobs'].extend({'item': item['displayName'], 'job_id': j['id'], 'status': j['status']}
                                      for j in jobs if j['status'] not in TERMINAL_JOBS)
        if item['type'] == 'Notebook':
            sessions = values(f"workspaces/{ws}/notebooks/{item['id']}/livySessions")
            row['active_spark_sessions'].extend({'item': item['displayName'], 'session_id': s['livyId'], 'state': s['state']}
                                                for s in sessions if s['state'] not in TERMINAL_SESSIONS)
        if item['type'] == 'DataPipeline':
            schedules = values(f"workspaces/{ws}/items/{item['id']}/jobs/Pipeline/schedules")
            row['enabled_pipeline_schedules'].extend({'item': item['displayName'], 'schedule_id': s['id']}
                                                     for s in schedules if s['enabled'])
    report['workspaces'].append(row)
    print(json.dumps({'workspace': alias, 'active_jobs': len(row['active_jobs']),
                      'active_sessions': len(row['active_spark_sessions']),
                      'enabled_schedules': len(row['enabled_pipeline_schedules'])}), flush=True)
report['batch_idle'] = all(not r[k] for r in report['workspaces']
                          for k in ['active_jobs', 'active_spark_sessions', 'enabled_pipeline_schedules'])
out = ROOT / 'evidence/fabric/operations/resource-audit-2026-11-13.json'
out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': 'resource_inventory_recorded', 'batch_idle': report['batch_idle']}), flush=True)
