"""Transporta apenas entradas imutáveis, sem tabelas ou recibos executados."""
import hashlib,json
from datetime import datetime,timezone
from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT,credential
from evidence import write_json
s=json.loads((ROOT/'.local/phase2-rebuild/binding.json').read_text())
dev=json.loads((ROOT/'.local/fabric-environment.json').read_text())
assert s['workspace_id']!=dev['workspace_id']
fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(s['workspace_id'])
prefix=s['lakehouse']['id']+'/Files/'
checks=[]
def upload(local,relative):
 content=local.read_bytes();sha=hashlib.sha256(content).hexdigest()
 target=prefix+relative
 fs.get_directory_client(target.rsplit('/',1)[0]).create_directory()
 client=fs.get_file_client(target)
 if not client.exists():
  client.create_file()
  for offset in range(0,len(content),4*1024*1024):
   block=content[offset:offset+4*1024*1024];client.append_data(block,offset=offset,length=len(block))
  client.flush_data(len(content))
 assert hashlib.sha256(client.download_file().readall()).hexdigest()==sha,'Entrada existente diferente: '+relative
 checks.append({'relative_path':relative,'bytes':len(content),'sha256':sha})
 print('Entrada imutável conferida:',relative,flush=True)
for binding,source in [('.local/national/bundle-binding.json','data/artifacts/national/bundle'),('.local/phase2-history/bundle.json','data/artifacts/history/bundle'),('.local/phase2-history/publication-bundle.json','data/artifacts/history/publication-bundle')]:
 b=json.loads((ROOT/binding).read_text());folder=ROOT/source
 assert hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest()==b['manifest_sha256']
 for path in sorted(folder.iterdir()):
  if path.is_file():upload(path,b['relative_path']+'/'+path.name)
 if (folder/'rules.zip').exists():
  sha=hashlib.sha256((folder/'rules.zip').read_bytes()).hexdigest()
  upload(folder/'rules.zip','shared_rules/'+sha+'/fuelwatch_history_rules.zip')
for name in ['population','weather_municipal_weekly']:
 path=ROOT/'data/artifacts/context'/(name+'.parquet');sha=hashlib.sha256(path.read_bytes()).hexdigest()
 upload(path,'context/'+sha+'/'+path.name)
write_json(ROOT/'evidence/phase2/deployment/rebuild-inputs.json',{'status':'immutable_rebuild_inputs_verified','environment':'fabric_rebuild','files':checks,'delta_tables_copied':False,'execution_receipts_copied':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
