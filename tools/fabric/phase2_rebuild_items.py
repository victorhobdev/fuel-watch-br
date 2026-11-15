"""Cria os itens básicos no workspace limpo; operações são retomáveis por ID."""
import json,time
from datetime import datetime,timezone
from client import ROOT,request
from evidence import write_json
folder=ROOT/'.local/phase2-rebuild';binding=folder/'binding.json'
s=json.loads(binding.read_text());c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
assert s['workspace_id']!=c['workspace_id']
base='workspaces/'+s['workspace_id']
workspace=request('GET',base).json()
capacity=next(x for x in request('GET','capacities').json()['value'] if x['id']==workspace['capacityId'])
assert capacity['sku'].startswith('FTL') and capacity['state']=='Active'
for key,collection,name in [('lakehouse','lakehouses','lh_fuelwatch'),('warehouse','warehouses','wh_fuelwatch')]:
 entry=s.setdefault(key,{})
 if not entry.get('id') and not entry.get('operation_location'):
  matches=[x for x in request('GET',base+'/items').json()['value'] if x['displayName']==name]
  assert len(matches)<=1
  if matches:entry['id']=matches[0]['id']
  else:
   entry['intent_at_utc']=datetime.now(timezone.utc).isoformat();write_json(binding,s)
   response=request('POST',base+'/'+collection,{'displayName':name,'description':'Phase 2 clean reconstruction; existing trial'})
   entry['http_status']=response.status_code
   if response.status_code==201:entry['id']=response.json()['id']
   else:
    assert response.status_code==202
    entry['operation_location']=response.headers['Location']
   write_json(binding,s)
 if not entry.get('id'):
  for i in range(60):
   op=request('GET',entry['operation_location']).json();entry['operation_status']=op['status'];write_json(binding,s)
   print(key,op['status'],flush=True)
   assert op['status']!='Failed',op.get('error')
   if op['status']=='Succeeded':
    entry['id']=request('GET',entry['operation_location'].rstrip('/')+'/result').json()['id'];write_json(binding,s);break
   assert i<59,'Retomar mesma operação sem recriar'
   time.sleep(10)
 actual=request('GET',base+'/'+collection+'/'+entry['id']).json()
 write_json(folder/(key+'-item.private.json'),actual)
 print('Item de reconstrução conferido:',key,flush=True)
write_json(ROOT/'evidence/phase2/deployment/rebuild-items.json',{'status':'clean_rebuild_core_items_created','environment':'fabric','workspace_id':s['workspace_id'],'lakehouse_id':s['lakehouse']['id'],'warehouse_id':s['warehouse']['id'],'capacity_sku':capacity['sku'],'data_execution_validated':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
