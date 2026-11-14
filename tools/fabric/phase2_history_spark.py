"""Preparar notebook historico e iniciar uma tentativa serial rastreavel."""
import argparse,base64,hashlib,json,re,time
from datetime import datetime,timezone
from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT,request,definition_operation,credential
from evidence import write_json

p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
g.add_argument('--prepare',action='store_true');g.add_argument('--start',metavar='ATTEMPT');g.add_argument('--watch',metavar='JOB_ID')
p.add_argument('--landing-run-id');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/phase2-history';binding=folder/'binding.json'
state=json.loads(binding.read_text());bundle=json.loads((folder/'bundle.json').read_text());base=f"workspaces/{c['workspace_id']}";name='11_historico_bronze_silver'
if args.prepare:
    ws=request('GET',base).json();cap=next(x for x in request('GET','capacities').json()['value'] if x['id']==ws['capacityId'])
    assert cap['sku'].startswith('FTL') and cap['state']=='Active'
    fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id'])
    prefix=c['lakehouse_id']+'/Files/'+bundle['relative_path'];fs.get_directory_client(prefix).create_directory()
    for path in sorted((ROOT/'data/artifacts/history/bundle').iterdir()):
        content=path.read_bytes();target=fs.get_file_client(prefix+'/'+path.name)
        if not target.exists():
            target.create_file()
            for offset in range(0,len(content),4*1024*1024):
                chunk=content[offset:offset+4*1024*1024];target.append_data(chunk,offset=offset,length=len(chunk))
            target.flush_data(len(content))
        assert hashlib.sha256(target.download_file().readall()).hexdigest()==hashlib.sha256(content).hexdigest(),path.name
        print('Historical input verified',path.name,flush=True)
    nb=json.loads((ROOT/'notebooks/11_historico_bronze_silver.ipynb').read_text(encoding='utf8'))
    nb['metadata']['dependencies']={'lakehouse':{'default_lakehouse':c['lakehouse_id'],'default_lakehouse_name':'lh_fuelwatch','default_lakehouse_workspace_id':c['workspace_id'],'known_lakehouses':[{'id':c['lakehouse_id']}]}}
    definition={'format':'ipynb','parts':[{'path':'notebook-content.ipynb','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(nb,ensure_ascii=False).encode()).decode()}]}
    matches=[x for x in request('GET',base+'/items').json()['value'] if x['displayName']==name];assert len(matches)<=1
    if not state.get('notebook_id'):
        item=matches[0] if matches else definition_operation(base+'/notebooks',{'displayName':name,'description':'Historico nacional: versoes, qualidade e comparacao tipada independente','definition':definition})
        state['notebook_id']=item['id'];write_json(binding,state)
    else:definition_operation(base+'/notebooks/'+state['notebook_id']+'/updateDefinition',{'definition':definition})
    readback=definition_operation(base+'/notebooks/'+state['notebook_id']+'/getDefinition?format=ipynb')
    actual=json.loads(base64.b64decode(next(x for x in readback['definition']['parts'] if x['path'].endswith('.ipynb'))['payload']))
    assert [x['source'] for x in actual['cells']]==[x['source'] for x in nb['cells']]
    write_json(folder/'notebook-readback.private.json',readback)
    print('Historical Spark notebook prepared; no job started',flush=True)
    raise SystemExit(0)
jobs=base+'/items/'+state['notebook_id']+'/jobs'
if args.start:
    assert re.fullmatch('[a-z0-9_-]+',args.start) and re.fullmatch('[0-9a-f-]{36}',args.landing_run_id or '')
    journal=folder/(args.start+'-spark-accepted.json');pending=folder/(args.start+'-spark-pending.json')
    assert not journal.exists() and not pending.exists(),'Retomar tentativa registrada; nao duplicar'
    for item in request('GET',base+'/items').json()['value']:
        if item['type']=='Notebook':
            sessions=request('GET',base+'/notebooks/'+item['id']+'/livySessions').json()
            assert not sessions.get('continuationToken'),'Inspecionar paginacao de sessoes'
            assert all(x['state'] in {'Succeeded','Failed','Cancelled','Dead','Error','Success'} for x in sessions['value']),'Sessao Spark ativa: acompanhar em vez de competir'
    write_json(pending,{'intent_at_utc':datetime.now(timezone.utc).isoformat(),'landing_run_id':args.landing_run_id})
    parameters={'p_landing_run_id':{'value':args.landing_run_id,'type':'string'},'p_bundle_relative_path':{'value':bundle['relative_path'],'type':'string'},'p_manifest_sha256':{'value':bundle['manifest_sha256'],'type':'string'}}
    response=request('POST',jobs+'/RunNotebook/instances',{'executionData':{'parameters':parameters}})
    job=response.headers['Location'].rstrip('/').split('/')[-1]
    write_json(journal,{'job_id':job,'landing_run_id':args.landing_run_id,'accepted_at_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':bundle['manifest_sha256']});pending.unlink()
    print('Accepted historical Spark job',job,flush=True)
else:job=args.watch
deadline=time.monotonic()+1800
while True:
    actual=request('GET',jobs+'/instances/'+job).json();write_json(folder/('spark-job-'+job+'.json'),actual)
    print(json.dumps({'job_id':job,'status':actual['status'],'failure':actual.get('failureReason')}),flush=True)
    if actual['status'] in {'Completed','Failed','Cancelled','Deduped'}:break
    assert time.monotonic()<deadline,'Retomar este mesmo job_id'
    time.sleep(30)
