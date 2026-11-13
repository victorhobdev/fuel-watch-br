"""Preparacao/execucao nacional via API e OneLake; nunca repete inicio automaticamente."""
import argparse,base64,json,hashlib,time
from datetime import datetime,timezone
from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT,request,definition_operation,credential

p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare',action='store_true');g.add_argument('--start',action='store_true');g.add_argument('--watch');p.add_argument('--retry-failed',action='store_true');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/national';folder.mkdir(exist_ok=True);binding=folder/'fabric-binding.json';base=f"workspaces/{c['workspace_id']}";name='10_brasil_todos_combustiveis'
if args.prepare:
 capid=request('GET',base).json()['capacityId'];cap=next(x for x in request('GET','capacities').json()['value'] if x['id']==capid);assert cap['sku'].startswith('FTL') and cap['state']=='Active'
 b=json.loads((folder/'bundle-binding.json').read_text());fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id']);prefix=c['lakehouse_id']+'/Files/'+b['relative_path'];fs.get_directory_client(prefix).create_directory()
 for path in sorted((ROOT/'data/artifacts/national/bundle').iterdir()):
  raw=path.read_bytes();f=fs.get_file_client(prefix+'/'+path.name)
  if f.exists():assert f.download_file().readall()==raw
  else:
   f.create_file();f.append_data(raw,offset=0,length=len(raw));f.flush_data(len(raw))
  assert hashlib.sha256(f.download_file().readall()).hexdigest()==hashlib.sha256(raw).hexdigest()
  print('Verified input '+path.name,flush=True)
 print('Immutable national bundle uploaded and read back',flush=True)
 items=request('GET',base+'/items').json()['value'];matches=[x for x in items if x['displayName']==name];assert len(matches)<=1
 item=matches[0] if matches else definition_operation(base+'/notebooks',{'displayName':name,'description':'ANP nacional: todos os combustiveis, qualidade e unidades preservadas; trial existente'})
 s={'notebook_id':item['id'],'workspace_id':c['workspace_id'],**b};binding.write_text(json.dumps(s,indent=2))
 nb=json.loads((ROOT/'notebooks/10_brasil_todos_combustiveis.ipynb').read_text(encoding='utf8'));nb['metadata']['dependencies']={'lakehouse':{'default_lakehouse':c['lakehouse_id'],'default_lakehouse_name':'lh_fuelwatch','default_lakehouse_workspace_id':c['workspace_id'],'known_lakehouses':[{'id':c['lakehouse_id']}]}}
 definition={'format':'ipynb','parts':[{'path':'notebook-content.ipynb','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(nb,ensure_ascii=False).encode()).decode()}]};definition_operation(base+'/notebooks/'+item['id']+'/updateDefinition',{'definition':definition});actual=definition_operation(base+'/notebooks/'+item['id']+'/getDefinition?format=ipynb');(folder/'notebook-readback.json').write_text(json.dumps(actual,indent=2));read=json.loads(base64.b64decode(next(x for x in actual['definition']['parts'] if x['path'].endswith('.ipynb'))['payload']));assert [x['source'] for x in read['cells']]==[x['source'] for x in nb['cells']];print('National notebook prepared and verified; no job started',flush=True);raise SystemExit(0)
s=json.loads(binding.read_text());jobs=base+'/items/'+s['notebook_id']+'/jobs';accepted=folder/'job-accepted.json'
if args.start:
 if accepted.exists():
  old=json.loads(accepted.read_text());state=request('GET',jobs+'/instances/'+old['job_id']).json();assert args.retry_failed and state['status']=='Failed','Acompanhar tentativa existente; nao duplicar';(folder/('accepted-'+old['job_id']+'.json')).write_text(json.dumps(old,indent=2))
 items=request('GET',base+'/items').json()['value']
 for item in items:
  if item['type']=='Notebook':
   sessions=request('GET',base+'/notebooks/'+item['id']+'/livySessions').json()['value'];assert all(x['state'] in {'Succeeded','Failed','Cancelled','Dead','Error','Success'} for x in sessions),'Sessao Spark ativa'
  elif item['type'] in {'DataPipeline','Dataflow'}:
   history=request('GET',base+'/items/'+item['id']+'/jobs/instances').json();assert not history.get('continuationToken');assert all(x['status'] in {'Completed','Failed','Cancelled','Deduped'} for x in history['value']),'Job ativo'
 pending=folder/'submission-pending.json'
 assert not pending.exists(),'Submissao anterior incerta: consultar historico antes de iniciar outro job'
 pending.write_text(json.dumps({'intent_at_utc':datetime.now(timezone.utc).isoformat(),'notebook_id':s['notebook_id']},indent=2))
 r=request('POST',jobs+'/RunNotebook/instances',{});loc=r.headers['Location'];job=loc.rstrip('/').split('/')[-1];accepted.write_text(json.dumps({'job_id':job,'location':loc,'accepted_at_utc':datetime.now(timezone.utc).isoformat()},indent=2));pending.unlink();print('Accepted national job '+job,flush=True)
else:job=args.watch
while True:
 state=request('GET',jobs+'/instances/'+job).json();(folder/('job-'+job+'.json')).write_text(json.dumps(state,indent=2));print(json.dumps({'job_id':job,'status':state['status'],'failure':state.get('failureReason')}),flush=True)
 if state['status'] in {'Completed','Failed','Cancelled','Deduped'}:break
 time.sleep(30)
