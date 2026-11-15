"""Emissão finita em fases com reconciliação de IDs antes de avançar."""
import hashlib,json,time
from datetime import datetime,timezone
from azure.eventhub import EventData,EventHubProducerClient,TransportType
from client import ROOT,request
from kusto import execute,rows
from evidence import write_json

c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
s=json.loads((ROOT/'.local/m10-api/binding.json').read_text())
m=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
state=json.loads((ROOT/'evidence/phase2/streaming/rule-state.json').read_text())
assert state['rule_running']
seed=json.loads((ROOT/'evidence/phase2/streaming/seed-check.json').read_text());assert seed['lab_run_id']==m['lab_run_id']
folder=ROOT/'.local/phase2-streaming'/m['lab_run_id']
base=f"workspaces/{c['workspace_id']}/eventstreams/{s['eventstream']['id']}"
def count():
 return rows(execute('declare query_parameters(p_run:string); lab_historical_events | where lab_run_id==p_run | summarize received=count(),unique_ids=dcount(event_id)',parameters={'p_run':m['lab_run_id']}))[0]
assert count()=={'received':10,'unique_ids':10},'Inspecionar lote existente antes de enviar'
for phase in ['baseline','transition','reinject']:
 assert not (folder/(phase+'-emission.json')).exists(),'Fase já registrada; não reenviar'
try:
 request('POST',base+'/resume',{'startType':'WhenLastStopped'})
 for i in range(20):
  topology=request('GET',base+'/topology').json()
  if all(x['status']=='Running' for x in topology['destinations']):break
  assert i<19,'Destinos indisponíveis'
  time.sleep(15)
 connection=request('GET',base+'/sources/'+s['source_id']+'/connection').json()
 client=EventHubProducerClient.from_connection_string(connection['accessKeys']['primaryConnectionString'],eventhub_name=connection['eventHubName'],transport_type=TransportType.AmqpOverWebsocket,retry_total=0,logging_enable=False)
 with client:
  for phase,expected_total,expected_unique in [('baseline',999,999),('transition',1000,1000),('reinject',1020,1000)]:
   payload=(folder/(phase+'.jsonl')).read_bytes()
   assert hashlib.sha256(payload).hexdigest()==m['files'][phase+'.jsonl']['sha256']
   record={'phase':phase,'status':'sending','started_at_utc':datetime.now(timezone.utc).isoformat(),'rows':m['files'][phase+'.jsonl']['rows']}
   journal=folder/(phase+'-emission.json');write_json(journal,record)
   batch=client.create_batch(partition_key=m['lab_run_id'])
   for line in payload.splitlines():
    event=EventData(line.decode());event.content_type='application/json';batch.add(event)
   client.send_batch(batch,timeout=60)
   record['status']='acknowledged_ingestion_pending';write_json(journal,record)
   print('Fase confirmada pelo transporte:',phase,flush=True)
   for i in range(40):
    actual=count();print(phase,actual,flush=True)
    if actual['received']==expected_total and actual['unique_ids']==expected_unique:break
    assert actual['received']<=expected_total and i<39,'Ingestão fora do esperado; inspecionar antes de repetir'
    time.sleep(15)
   record.update(status='ingestion_counts_verified',actual=actual,finished_at_utc=datetime.now(timezone.utc).isoformat());write_json(journal,record)
finally:
 request('POST',base+'/pause')
 for i in range(20):
  topology=request('GET',base+'/topology').json()
  if all(x['status']=='Paused' for x in topology['destinations']):break
  assert i<19,'Conferir pausa dos destinos'
  time.sleep(15)
 write_json(ROOT/'evidence/phase2/streaming/post-emission-topology.json',{'destinations_paused':True,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('Emissão finita encerrada; destinos pausados; comparação completa e ação pendentes',flush=True)
