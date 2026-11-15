"""Vincula tabela histórica ao destino existente e encerra com destinos pausados."""
import base64
import json
import time
from datetime import datetime,timezone
from client import ROOT,request,definition_operation
from evidence import write_json

c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
s=json.loads((ROOT/'.local/m10-api/binding.json').read_text())
folder=ROOT/'.local/phase2-streaming'
folder.mkdir(exist_ok=True)
base=f"workspaces/{c['workspace_id']}/eventstreams/{s['eventstream']['id']}"
before=definition_operation(base+'/getDefinition')
write_json(folder/'destination-before.private.json',before)
part=next(p for p in before['definition']['parts'] if p['path']=='eventstream.json')
topology=json.loads(base64.b64decode(part['payload']))
target=next(d for d in topology['destinations'] if d['name']=='synthetic_eventhouse')
assert target['properties']['tableName'] in {'lab_preco_eventos','lab_historical_events'}
target['properties']['tableName']='lab_historical_events'
part['payload']=base64.b64encode(json.dumps(topology).encode()).decode()
definition_operation(base+'/updateDefinition',{'definition':before['definition']})
actual=definition_operation(base+'/getDefinition')
found=json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path']=='eventstream.json')['payload']))
assert next(d for d in found['destinations'] if d['name']=='synthetic_eventhouse')['properties']['tableName']=='lab_historical_events'
status=request('GET',base+'/topology').json()
if any(d['status']!='Paused' for d in status['destinations']):
 request('POST',base+'/pause')
for attempt in range(20):
 status=request('GET',base+'/topology').json()
 if all(d['status']=='Paused' for d in status['destinations']):break
 assert attempt<19,'Retomar observação; destinos ainda em transição'
 time.sleep(15)
write_json(ROOT/'evidence/phase2/streaming/destination.json',{
 'status':'historical_destination_bound_and_paused','environment':'fabric',
 'table':'lab_historical_events','destinations':[{'name':d['name'],'status':d['status']} for d in status['destinations']],
 'emitter_started':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('Destino histórico conferido; todos os destinos pausados; nenhum evento emitido',flush=True)
