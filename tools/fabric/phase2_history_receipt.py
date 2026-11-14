"""Recuperar recibo imutavel da execucao historica concluida no Fabric."""
import argparse,json
from datetime import datetime,timezone
from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT,request,credential
from evidence import write_json

p=argparse.ArgumentParser();p.add_argument('job_id');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());state=json.loads((ROOT/'.local/phase2-history/binding.json').read_text())
job=request('GET',f"workspaces/{c['workspace_id']}/items/{state['notebook_id']}/jobs/instances/{args.job_id}").json()
assert job['status']=='Completed',job['status']
def utc(value):return datetime.fromisoformat(value.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
start,end=utc(job['startTimeUtc']),utc(job['endTimeUtc'])
fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id'])
receipts=[]
for path in fs.get_paths(path=c['lakehouse_id']+'/Files/audit/history'):
    if path.name.endswith('.json'):
        receipt=json.loads(fs.get_file_client(path.name).download_file().readall())
        if start<=utc(receipt['started_at_utc'])<=utc(receipt['finished_at_utc'])<=end:
            receipts.append(receipt)
assert len(receipts)==1,'Recibo ambiguo ou ausente'
receipt=receipts[0];assert receipt['status']=='historical_versions_silver_validated'
expected=json.loads((ROOT/'evidence/phase2/history/reference-summary.json').read_text(encoding='utf8'))['sources']
assert len(receipt['sources'])==len(expected)
for actual in receipt['sources']:
    reference=next(x for x in expected if x['source_id']==actual['source_id'])
    assert actual['source_sha256']==reference['source_sha256'] and actual['full_typed_comparison_passed'] is True
    counts=actual['counts'];e=reference['counts']
    assert counts=={'selected':e['received'],'invalid':e['invalid'],'exact_duplicate_excess':e['exact_duplicate_excess'],'conflicting_rows_after_exact_dedup':e['conflicting_rows'],'accepted':e['accepted']}
write_json(ROOT/'evidence/phase2/history'/('silver-'+args.job_id+'.json'),{'status':'historical_silver_receipt_verified','job_id':args.job_id,'job_status':job['status'],'environment':'fabric','receipt':receipt,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print(json.dumps({'status':'historical_silver_receipt_verified','job_id':args.job_id,'accepted':sum(x['counts']['accepted'] for x in receipt['sources'])}),flush=True)
