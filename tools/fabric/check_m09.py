"""Reconcilia cada medicao Spark com a projecao Gold por SQL real."""
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone

from azure.storage.filedatalake import DataLakeServiceClient

from client import ROOT, credential, request, environment_config
from warehouse import connect

config = environment_config()
alias = config.get('benchmark_workspace_alias', 'dev')
assert alias in {'dev', 'test'}
folder = ROOT / ('.local/m09-test-api' if alias == 'test' else '.local/m09-api')
binding = json.loads((folder / 'binding.json').read_text())
accepted = json.loads((folder / 'accepted.json').read_text())
job = request('GET', f"workspaces/{config['workspace_id']}/items/{binding['notebook_id']}/jobs/instances/{accepted['job_id']}").json()
(folder / ('job-' + accepted['job_id'] + '.json')).write_text(json.dumps(job, indent=2))
assert job['status'] == 'Completed', job
fs = DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com', credential=credential).get_file_system_client(config['workspace_id'])
root = config['lakehouse_id'] + '/Files/audit/m09'
matches = []
def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)

job_start, job_end = utc(job['startTimeUtc']), utc(job['endTimeUtc'])
for path in fs.get_paths(path=root):
    if path.name.endswith('/summary.json'):
        audit = json.loads(fs.get_file_client(path.name).download_file().readall())
        # O job pode iniciar antes da resposta HTTP chegar ao cliente.
        if job_start <= utc(audit['started_at_utc']) <= utc(audit['finished_at_utc']) <= job_end:
            matches.append((path.name, audit))
assert len(matches) == 1, 'Exigir um unico receipt novo; nao usar latest'
path, audit = matches[0]
assert audit['status'] == 'benchmark_measured', audit
assert audit['shuffle_restored'] and audit['source_version_unchanged']
assert not audit['official_tables_written'] and not audit['production_configuration_changed']
weekly = json.loads(fs.get_file_client(path.rsplit('/', 1)[0] + '/weekly-business.json').download_file().readall())
assert len(weekly) == 656
fields = ['inicio_semana_iso', 'ano_iso', 'semana_iso', 'municipio_ibge', 'produto', 'moeda', 'unidade',
          'coletas', 'postos_observados', 'soma_precos', 'preco_minimo', 'preco_maximo', 'precos_incomuns']
with connect() as connection:
    started = time.perf_counter()
    cursor = connection.cursor().execute('SELECT ' + ','.join(fields) + ' FROM gold.preco_semanal')
    sql_rows = sorted([[None if value is None else str(value) for value in row] for row in cursor.fetchall()])
    sql_seconds = time.perf_counter() - started
assert sql_rows == weekly, 'Diferenca completa Spark versus Gold'
fingerprint = hashlib.sha256(json.dumps(weekly).encode()).hexdigest()
assert len(audit['samples']) == 6 and len(audit['warmups']) == 2
for phase, partitions in [('baseline', 200), ('intervention', 8)]:
    samples = [sample for sample in audit['samples'] if sample['phase'] == phase]
    assert len(samples) == 3 and sorted(s['iteration'] for s in samples) == [1, 2, 3]
    assert all(s['business_sha256'] == fingerprint and s['shuffle_partitions'] == partitions for s in samples)
    assert statistics.median(s['seconds'] for s in samples) == audit['medians_seconds'][phase]
baseline, changed = (audit['medians_seconds'][phase] for phase in ['baseline', 'intervention'])
verification = {'status': 'benchmark_reconciled', 'environment': 'fabric', 'job_id': accepted['job_id'],
    'workspace_alias': alias,
    'experiment_id': audit['experiment_id'], 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    'measured_samples': 6, 'excluded_warmups': 2, 'source_rows': audit['input_rows'],
    'weekly_groups': len(weekly), 'full_columns_compared': fields, 'full_sql_comparison_passed': True,
    'business_sha256': fingerprint, 'medians_seconds': audit['medians_seconds'],
    'relative_median_change_percent': (changed / baseline - 1) * 100,
    'gold_select_seconds_single_observation': sql_seconds,
    'shuffle_restored': audit['shuffle_restored'], 'source_version_unchanged': audit['source_version_unchanged'],
    'production_configuration_changed': False, 'cost_or_cu_measured': False,
    'limits': ['n=3 per phase', 'fixed baseline then intervention order', 'warm cached input',
               'same session on shared trial, not capacity isolation', 'no end-to-end pipeline speedup claim']}
out = ROOT / 'evidence/fabric/performance' / audit['experiment_id']
out.mkdir(parents=True, exist_ok=True)
for name, data in [('summary.json', audit), ('verification.json', verification), ('weekly-business.json', weekly),
                   ('job.json', job)]:
    # Job payload may contain identity fields; keep original private, track only safe projection.
    if name == 'job.json':
        data = {key: job.get(key) for key in ['id', 'jobType', 'invokeType', 'status', 'startTimeUtc', 'endTimeUtc', 'failureReason']}
    (out / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
for sample in audit['samples'] + audit['warmups']:
    raw = fs.get_file_client(path.rsplit('/', 1)[0] + '/' + sample['plan_file']).download_file().readall()
    assert hashlib.sha256(raw).hexdigest() == sample['plan_sha256']
    (folder / sample['plan_file']).write_bytes(raw)
print(json.dumps(verification), flush=True)
