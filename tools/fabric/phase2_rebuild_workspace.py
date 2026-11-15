"""Prepara workspace vazio na capacidade trial existente; não implanta dados."""
import json,time
from datetime import datetime,timezone
from client import ROOT,request,definition_operation
from evidence import write_json
c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
folder=ROOT/'.local/phase2-rebuild';folder.mkdir(exist_ok=True)
binding=folder/'binding.json'
state=json.loads(binding.read_text()) if binding.exists() else {}
dev=request('GET','workspaces/'+c['workspace_id']).json()
capacity=next(x for x in request('GET','capacities').json()['value'] if x['id']==dev['capacityId'])
assert capacity['sku'].startswith('FTL') and capacity['state']=='Active','Somente trial existente'
if not state.get('workspace_id'):
 matches=[x for x in request('GET','workspaces').json()['value'] if x['displayName']=='fuelwatch-rebuild-f2']
 assert len(matches)<=1
 item=matches[0] if matches else definition_operation('workspaces',{'displayName':'fuelwatch-rebuild-f2','description':'Fuel Watch phase 2 reproducibility laboratory; existing trial only'})
 state['workspace_id']=item['id'];write_json(binding,state)
assert state['workspace_id']!=c['workspace_id']
base='workspaces/'+state['workspace_id']
workspace=request('GET',base).json()
if workspace.get('capacityId')!=capacity['id']:
 response=request('POST',base+'/assignToCapacity',{'capacityId':capacity['id']})
 write_json(folder/'capacity-assignment.json',{'status':response.status_code,'location':response.headers.get('Location')})
for i in range(30):
 workspace=request('GET',base).json()
 if workspace.get('capacityId')==capacity['id'] and workspace.get('capacityAssignmentProgress') in {None,'Completed'}:break
 assert i<29,'Retomar atribuição existente sem repetir criação'
 time.sleep(10)
items=request('GET',base+'/items').json()
assert not items.get('continuationToken') and items['value']==[],'Workspace não vazio; não apagar itens'
write_json(ROOT/'evidence/phase2/deployment/empty-workspace.json',{'status':'empty_rebuild_workspace_verified','environment':'fabric','workspace_id':state['workspace_id'],'item_count':0,'capacity_sku':capacity['sku'],'same_trial_as_dev':True,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('Workspace de reconstrução vazio confirmado na mesma capacidade trial',flush=True)
