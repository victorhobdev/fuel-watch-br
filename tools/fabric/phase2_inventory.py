"""Inventário atual de recursos; classificação inicial não substitui dependências."""
import json
from datetime import datetime,timezone
from client import ROOT,request
from evidence import write_json
c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
base='workspaces/'+c['workspace_id']
items=[];path=base+'/items'
while path:
 page=request('GET',path).json();items.extend(page['value'])
 token=page.get('continuationToken')
 if token:
  from urllib.parse import quote
  path=base+'/items?continuationToken='+quote(token,safe='')
 else:path=None
active={'lh_fuelwatch','wh_fuelwatch','pl_fuelwatch_historico','11_historico_bronze_silver','12_historico_publicacao','15_context_references','sm_fuelwatch_historico','Fuel Watch BR Histórico'}
rows=[{'id':x['id'],'name':x['displayName'],'type':x['type'],'review_group':'active_candidate' if x['displayName'] in active else 'requires_dependency_review'} for x in items]
write_json(ROOT/'evidence/phase2/deployment/inventory.json',{'status':'current_items_inventoried_dependency_review_pending','environment':'fabric','checked_at_utc':datetime.now(timezone.utc).isoformat(),'item_count':len(rows),'items':rows})
print('Itens atuais inventariados:',len(rows),flush=True)
