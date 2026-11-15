"""Instala notebooks versionados com Lakehouse isolado no destino de reconstrução."""
import base64,json,argparse
from datetime import datetime,timezone
from client import ROOT,request,definition_operation
from evidence import write_json
folder=ROOT/'.local/phase2-rebuild';binding=folder/'binding.json'
s=json.loads(binding.read_text());dev=json.loads((ROOT/'.local/fabric-environment.json').read_text())
assert s['workspace_id']!=dev['workspace_id'] and s['lakehouse']['id']!=dev['lakehouse_id']
base='workspaces/'+s['workspace_id']
wh=request('GET',base+'/warehouses/'+s['warehouse']['id']).json()
environment={'workspace_id':s['workspace_id'],'lakehouse_id':s['lakehouse']['id'],'warehouse_database':'wh_fuelwatch','warehouse_server':wh['properties']['connectionInfo']}
write_json(folder/'environment.json',environment)
s.setdefault('notebooks',{})
checks=[]
parser=argparse.ArgumentParser();parser.add_argument('--only');args=parser.parse_args()
for name in ['01_landing_to_bronze','10_brasil_todos_combustiveis','11_historico_bronze_silver','12_historico_publicacao','15_context_references']:
 if args.only and args.only!=name:continue
 nb=json.loads((ROOT/'notebooks'/(name+'.ipynb')).read_text(encoding='utf8'))
 nb['metadata']['dependencies']={'lakehouse':{'default_lakehouse':s['lakehouse']['id'],'default_lakehouse_name':'lh_fuelwatch','default_lakehouse_workspace_id':s['workspace_id'],'known_lakehouses':[{'id':s['lakehouse']['id']}]}}
 encoded=json.dumps(nb,ensure_ascii=False)
 assert dev['workspace_id'] not in encoded and dev['lakehouse_id'] not in encoded,'Referência literal de desenvolvimento no notebook'
 definition={'format':'ipynb','parts':[{'path':'notebook-content.ipynb','payloadType':'InlineBase64','payload':base64.b64encode(encoded.encode()).decode()}]}
 if name not in s['notebooks']:
  matches=[i for i in request('GET',base+'/items').json()['value'] if i['displayName']==name];assert len(matches)<=1
  item=matches[0] if matches else definition_operation(base+'/notebooks',{'displayName':name,'definition':definition})
  s['notebooks'][name]=item['id'];write_json(binding,s)
 actual=definition_operation(base+'/notebooks/'+s['notebooks'][name]+'/getDefinition?format=ipynb')
 decoded=json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path'].endswith('.ipynb'))['payload']))
 assert [x['source'] for x in decoded['cells']]==[x['source'] for x in nb['cells']]
 assert decoded['metadata']['dependencies']['lakehouse']['default_lakehouse']==s['lakehouse']['id']
 checks.append({'notebook':name,'code_equal':True,'target_lakehouse_verified':True,'dev_literals_absent':True})
 print('Notebook de reconstrução conferido:',name,flush=True)
write_json(ROOT/'evidence/phase2/deployment/rebuild-notebooks.json',{'status':'rebuild_notebook_code_and_bindings_verified','environment':'fabric_rebuild','checks':checks,'workloads_executed':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
