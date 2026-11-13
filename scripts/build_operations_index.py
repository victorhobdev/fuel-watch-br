"""Deriva uma visao operacional das evidencias reais ja verificadas."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'evidence/fabric/operations'
out.mkdir(parents=True, exist_ok=True)
runs = []
for file in sorted((ROOT / 'evidence/fabric/orchestration/pipeline-runs').glob('*/verification.json')):
    verified = json.loads(file.read_text())
    def child(name):
        path = file.parent / name
        return json.loads(path.read_text()) if path.exists() else {}
    bronze, silver = child('bronze-child.json'), child('silver-child.json')
    export = child('export-child.json')
    publication = verified.get('publication', [])
    publications = publication if isinstance(publication, list) else [publication]
    runs.append({'root_run_id': verified['job_id'], 'job_status': verified['job_status'],
        'fault_stage': verified['fault_stage'], 'invoke_type': verified.get('invoke_type'),
        'start_utc': verified.get('job_start_utc'), 'end_utc': verified.get('job_end_utc'),
        'bronze_run_id': bronze.get('run_id'), 'bronze_rows': bronze.get('source_rows'),
        'raw_bytes': bronze.get('raw_bytes'), 'source_sha256': bronze.get('source_sha256'),
        'silver_run_id': silver.get('run_id'), 'silver_status': silver.get('status'),
        'silver_counts': silver.get('counts'), 'ibge_sha256': silver.get('ibge_sha256'),
        'export_batch_id': export.get('batch_id'), 'export_status': export.get('status'),
        'publication': publications, 'warehouse_attempt': verified.get('warehouse_attempt'),
        'previous_publication_unchanged': verified.get('previous_publication_unchanged'),
        'activities': verified['activities'], 'business_fingerprints': verified['business_fingerprints'],
        'evidence_path': file.relative_to(ROOT).as_posix()})
assert len(runs) == 7 and any(r['job_status'] == 'Failed' for r in runs)
report = {'status': 'derived_from_verified_fabric_evidence', 'environment': 'fabric',
          'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'runs': runs,
          'null_semantics': 'Nao registrado/não produzido; nunca assumir zero.',
          'performance_baseline_claimed': False}
(out / 'execution-index-2026-11-13.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

inventory = json.loads((ROOT / '.local/m09-api/inventory.json').read_text())
public = {'captured_at_utc': inventory['captured_at_utc'], 'environment': 'fabric',
          'workspace_alias': 'DEV', 'capacity': {key: inventory['capacity'][key] for key in ['sku', 'region', 'state']},
          'trial_expiration_verified': False, 'trial_expiration_utc': None,
          'spark_settings': inventory['spark_settings'],
          'items': [{'name': item['displayName'], 'type': item['type']} for item in inventory['items']],
          'inventory_timing': 'Antes da criacao do notebook de benchmark M09.',
          'paid_capacity_created': False}
(out / 'environment-inventory-2026-11-13.json').write_text(json.dumps(public, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('Operations index: seven verified runs; inventory redacted; no new Fabric execution')
