"""Envia dez eventos uma única vez e pausa os destinos ao encerrar."""
import hashlib,json,time,sys
from datetime import datetime,timezone
from azure.eventhub import EventData,EventHubProducerClient,TransportType
from client import ROOT,request
from evidence import write_json

c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
s=json.loads((ROOT/'.local/m10-api/binding.json').read_text())
m=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
folder=ROOT/'.local/phase2-streaming'/m['lab_run_id']
journal=folder/'seed-emission.json'
if journal.exists():
 assert '--retry-preflight' in sys.argv,'Inspecionar IDs e tentativa anterior; não repetir envio'
 previous=json.loads(journal.read_text())
 assert previous['status']=='unconfirmed' and previous.get('error_type')=='HTTPError' and previous.get('destinations_paused')
 from kusto import execute,rows
 assert rows(execute('declare query_parameters(p_run:string); lab_historical_events | where lab_run_id==p_run | count',parameters={'p_run':m['lab_run_id']}))==[{'Count':0}]
 write_json(folder/'seed-preflight-failure.json',previous)
base=f"workspaces/{c['workspace_id']}/eventstreams/{s['eventstream']['id']}"
payload=(folder/'seed.jsonl').read_bytes()
assert hashlib.sha256(payload).hexdigest()==m['files']['seed.jsonl']['sha256']
records=[json.loads(x) for x in payload.splitlines()]
assert len(records)==10 and all(x['alert_score']==0 for x in records)
record={'status':'preparing','lab_run_id':m['lab_run_id'],'rows':10,'started_at_utc':datetime.now(timezone.utc).isoformat()}
write_json(journal,record)
try:
 request('POST',base+'/resume',{'startType':'Now'})
 for i in range(20):
  topology=request('GET',base+'/topology').json()
  if all(x['status']=='Running' for x in topology['destinations']):break
  assert i<19,'Destinos não prontos; nenhum envio realizado'
  time.sleep(15)
 connection=request('GET',base+'/sources/'+s['source_id']+'/connection').json()
 client=EventHubProducerClient.from_connection_string(connection['accessKeys']['primaryConnectionString'],eventhub_name=connection['eventHubName'],transport_type=TransportType.AmqpOverWebsocket,retry_total=0,logging_enable=False)
 record['status']='sending';write_json(journal,record)
 with client:
  batch=client.create_batch(partition_key=m['lab_run_id'])
  for row in records:
   event=EventData(json.dumps(row,separators=(',',':')));event.content_type='application/json';batch.add(event)
  client.send_batch(batch,timeout=60)
 record['status']='acknowledged_ingestion_pending'
except Exception as exc:
 record['status']='unconfirmed';record['error_type']=type(exc).__name__
 if getattr(exc,'response',None) is not None:
  write_json(folder/'seed-http-error.private.json',{'status':exc.response.status_code,'body':exc.response.text})
 raise SystemExit('Tentativa não confirmada; inspecionar journal e KQL antes de repetir')
finally:
 write_json(journal,record)
 request('POST',base+'/pause')
 for i in range(20):
  topology=request('GET',base+'/topology').json()
  if all(x['status']=='Paused' for x in topology['destinations']):break
  assert i<19,'Conferir pausa dos destinos'
  time.sleep(15)
 record['destinations_paused']=True;record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
 write_json(journal,record)
 write_json(ROOT/'evidence/phase2/streaming/seed-emission.json',record)
print(json.dumps(record),flush=True)
