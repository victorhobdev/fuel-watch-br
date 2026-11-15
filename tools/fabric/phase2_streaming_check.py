"""Compara conjuntos, multiplicidades, payloads e classificação do lote recebido."""
import json,sys
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from client import ROOT
from kusto import execute,rows
from evidence import write_json
sys.path.insert(0,str(ROOT))
from fuelwatch.historical_events import classify_event
m=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
folder=ROOT/'.local/phase2-streaming'/m['lab_run_id']
expected=[json.loads(line) for phase in ['seed','baseline','transition','reinject'] for line in (folder/(phase+'.jsonl')).read_text().splitlines()]
actual=rows(execute('declare query_parameters(p_run:string); lab_historical_events | where lab_run_id==p_run',parameters={'p_run':m['lab_run_id']}))
assert len(actual)==len(expected)==1020
assert Counter(x['event_id'] for x in actual)==Counter(x['event_id'] for x in expected)
lookup={x['event_id']:x for x in expected}
for row in actual:
 reference=lookup[row['event_id']]
 for key,value in reference.items():
  if key=='event_time':assert datetime.fromisoformat(row[key].replace('Z','+00:00'))==datetime.fromisoformat(value)
  elif key in {'preco','alert_score'}:assert Decimal(str(row[key]))==Decimal(str(value)),(key,row)
  else:assert row[key]==value,(key,row[key],value)
 assert classify_event({**row,'preco':str(row['preco'])},m['benchmark'])==row['benchmark_status']
 assert row['alert_score']==int(row['benchmark_status']=='above_threshold')
unique={x['event_id']:x for x in actual}
counts=Counter(x['benchmark_status'] for x in unique.values())
assert dict(counts)==m['expected_classifications']
assert sum(x['is_late_fixture'] for x in unique.values())==10
write_json(ROOT/'evidence/phase2/streaming/payload-verification.json',{'status':'historical_synthetic_payloads_reconciled','environment':'fabric','lab_run_id':m['lab_run_id'],'received':1020,'unique_ids':1000,'reinjection_excess':20,'late_events':10,'full_payload_comparison':True,'classification_recomputed_independently':True,'classifications':dict(counts),'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('1.020 payloads conferidos; 1.000 IDs únicos; classificações recalculadas',flush=True)
