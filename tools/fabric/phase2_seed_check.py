"""Compara todos os campos dos dez eventos recebidos com a fixture imutável."""
import json
from datetime import datetime,timezone
from decimal import Decimal
from client import ROOT
from kusto import execute,rows
from evidence import write_json
m=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
expected=[json.loads(x) for x in (ROOT/'.local/phase2-streaming'/m['lab_run_id']/'seed.jsonl').read_text().splitlines()]
actual=rows(execute('declare query_parameters(p_run:string); lab_historical_events | where lab_run_id==p_run',parameters={'p_run':m['lab_run_id']}))
assert len(actual)==len(expected)==10
lookup={x['event_id']:x for x in actual}
assert len(lookup)==10 and set(lookup)=={x['event_id'] for x in expected}
for reference in expected:
 row=lookup[reference['event_id']]
 for key,value in reference.items():
  if key=='event_time':assert datetime.fromisoformat(row[key].replace('Z','+00:00'))==datetime.fromisoformat(value)
  elif key in {'preco','alert_score'}:assert Decimal(str(row[key]))==Decimal(str(value))
  else:assert row[key]==value,(key,row[key],value)
write_json(ROOT/'evidence/phase2/streaming/seed-check.json',{'status':'seed_full_payload_reconciled','environment':'fabric','lab_run_id':m['lab_run_id'],'unique_ids':10,'full_payload_comparison':True,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('Dez eventos: IDs e payloads completos reconciliados',flush=True)
