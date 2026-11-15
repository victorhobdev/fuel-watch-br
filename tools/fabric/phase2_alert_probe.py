"""Sonda finita após correção da ocorrência; mantém o lote original intacto."""
import json,time
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from azure.eventhub import EventData,EventHubProducerClient,TransportType
from client import ROOT,request
from warehouse import connect,results
from evidence import write_json
c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
s=json.loads((ROOT/'.local/m10-api/binding.json').read_text())
m=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
folder=ROOT/'.local/phase2-streaming'
journal=folder/'probe.json'
assert not journal.exists(),'Retomar observação da sonda existente; não reenviar'
assert json.loads((ROOT/'evidence/phase2/streaming/rule-state.json').read_text())['rule_running']
run=str(uuid4());stamp=datetime.now(timezone.utc)
original=[json.loads(x) for x in (folder/m['lab_run_id']/'transition.jsonl').read_text().splitlines()][0]
events=[]
for i in range(2):
 e={**original,'lab_run_id':run,'event_id':str(uuid4()),'posto_id':'SYNTHETIC_PROBE','sequence':i,'event_time':(stamp+timedelta(seconds=i)).isoformat(),'alert_score':i,'benchmark_status':'above_threshold' if i else 'within_threshold','preco':original['preco'] if i else m['benchmark']['median']}
 events.append(e)
record={'status':'preparing','probe_run_id':run,'parent_lab_run_id':m['lab_run_id'],'events':events,'started_at_utc':stamp.isoformat()}
write_json(journal,record)
base=f"workspaces/{c['workspace_id']}/eventstreams/{s['eventstream']['id']}"
try:
 request('POST',base+'/resume',{'startType':'Now'})
 for i in range(30):
  t=request('GET',base+'/topology').json()
  if all(d['status']=='Running' for d in t['destinations']):break
  assert i<29,'Destinos não disponíveis; envio não iniciado'
  time.sleep(15)
 connection=request('GET',base+'/sources/'+s['source_id']+'/connection').json()
 client=EventHubProducerClient.from_connection_string(connection['accessKeys']['primaryConnectionString'],eventhub_name=connection['eventHubName'],transport_type=TransportType.AmqpOverWebsocket,retry_total=0)
 record['status']='sending';write_json(journal,record)
 with client:
  for e in events:
   batch=client.create_batch(partition_key=run);batch.add(EventData(json.dumps(e)));client.send_batch(batch,timeout=60)
 record['status']='acknowledged_audit_pending';write_json(journal,record)
 print('Sonda de dois eventos confirmada pelo transporte',flush=True)
 with connect() as cn:
  cn.timeout=60
  for i in range(20):
   audit=results(cn.cursor().execute('SELECT * FROM lab_f2.alert_audit WHERE lab_run_id=?',m['lab_run_id']))[0]
   print('Linhas de auditoria:',len(audit),flush=True)
   if audit:
    record.update(status='audit_observed',audit=audit);break
   time.sleep(15)
  else:record['status']='audit_not_observed_within_window'
finally:
 write_json(journal,record)
 request('POST',base+'/pause')
 record['pause_requested']=True
 write_json(ROOT/'evidence/phase2/streaming/occurrence-probe.json',record)
print(json.dumps({'status':record['status'],'probe_run_id':run}),flush=True)
