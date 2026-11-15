"""Vincula o recibo OneLake ao job Spark concluído e aos hashes locais."""
import hashlib
import json
import sys
from datetime import datetime, timezone

from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT, credential, request
from evidence import write_json

job_id = sys.argv[1]
c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
state = json.loads((ROOT / '.local/phase2-context/binding.json').read_text())
job = request('GET', f"workspaces/{c['workspace_id']}/items/{state['notebook_id']}/jobs/instances/{job_id}").json()
assert job['status'] == 'Completed', job
def utc(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
start, end = utc(job['startTimeUtc']), utc(job['endTimeUtc'])
fs = DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com', credential=credential).get_file_system_client(c['workspace_id'])
receipts = []
for path in fs.get_paths(path=c['lakehouse_id'] + '/Files/audit/phase2_context'):
    if path.name.endswith('/summary.json'):
        receipt = json.loads(fs.get_file_client(path.name).download_file().readall())
        if start <= utc(receipt['started_at_utc']) <= utc(receipt['finished_at_utc']) <= end:
            receipts.append(receipt)
assert len(receipts) == 1, 'Recibo ausente ou ambíguo para o job'
receipt = receipts[0]
assert receipt['status'] == 'context_reference_tables_validated'
for name, expected_rows in [('population', 16713), ('weather_municipal_weekly', 48677)]:
    digest = hashlib.sha256((ROOT / 'data/artifacts/context' / (name + '.parquet')).read_bytes()).hexdigest()
    assert receipt['inputs'][name]['sha256'] == digest and receipt['inputs'][name]['rows'] == expected_rows
write_json(ROOT / 'evidence/phase2/context' / ('fabric-reference-' + job_id + '.json'),
    {'status': 'context_spark_receipt_verified', 'environment': 'fabric', 'job_id': job_id,
     'job_status': job['status'], 'receipt': receipt, 'checked_at_utc': datetime.now(timezone.utc).isoformat()})
print(json.dumps({'status': 'context_spark_receipt_verified', 'job_id': job_id, 'inputs': receipt['inputs']}, ensure_ascii=False))
