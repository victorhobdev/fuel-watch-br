"""Copy binario nacional parametrizado; acompanhar o mesmo RunId e validar hashes."""
import argparse
import base64
import copy
import hashlib
import json
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT, request, definition_operation, credential
from evidence import write_json

parser=argparse.ArgumentParser()
group=parser.add_mutually_exclusive_group(required=True)
group.add_argument('--prepare',action='store_true')
group.add_argument('--start',metavar='ATTEMPT')
group.add_argument('--watch',metavar='RUN_ID')
group.add_argument('--verify',metavar='RUN_ID')
args=parser.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
folder=ROOT/'.local/phase2-history';folder.mkdir(exist_ok=True)
binding=folder/'binding.json'
state=json.loads(binding.read_text()) if binding.exists() else {}
base=f"workspaces/{c['workspace_id']}"
name='pl_anp_historico_landing'
profiles=json.loads((ROOT/'evidence/phase2/history/profile-summary.json').read_text(encoding='utf8'))['profiles']
sources=[{'source_id':p['source_id'],'relative_url':urlparse(p['source_url']).path,'sha256':p['source_sha256'],'filename':p['source_url'].rsplit('/',1)[-1],'bytes':p['source_bytes']} for p in profiles]
assert len(sources)==4 and len({s['source_id'] for s in sources})==4

if args.prepare:
    ws=request('GET',base).json()
    cap=next(x for x in request('GET','capacities').json()['value'] if x['id']==ws['capacityId'])
    assert cap['sku'].startswith('FTL') and cap['state']=='Active'
    parent=definition_operation(base+'/dataPipelines/'+c['pipeline_id']+'/getDefinition')
    body=json.loads(base64.b64decode(next(p for p in parent['definition']['parts'] if p['path']=='pipeline-content.json')['payload']))
    activity=copy.deepcopy(next(a for a in body['properties']['activities'] if a['type']=='Copy'))
    activity['name']='Copy_Official_Version';activity['dependsOn']=[]
    tp=activity['typeProperties']
    tp['source']['datasetSettings']['typeProperties']['location']['relativeUrl']={'value':'@item().relative_url','type':'Expression'}
    target=tp['sink']['datasetSettings']
    assert target['linkedService']['properties']['typeProperties']['artifactId']==c['lakehouse_id']
    target['typeProperties']['location']['fileName']={'value':'@item().filename','type':'Expression'}
    target['typeProperties']['location']['folderPath']={'value':"@concat('landing/anp-history/',item().source_id,'/',pipeline().RunId)",'type':'Expression'}
    payload={'properties':{'activities':[{'name':'For_Each_Official_Version','type':'ForEach','dependsOn':[],
        'typeProperties':{'items':{'value':'@pipeline().parameters.p_sources','type':'Expression'},'isSequential':True,'activities':[activity]}}],
        'parameters':{'p_sources':{'type':'array','defaultValue':sources}}}}
    definition={'parts':[{'path':'pipeline-content.json','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(payload).encode()).decode()}]}
    matches=[x for x in request('GET',base+'/items').json()['value'] if x['displayName']==name]
    assert len(matches)<=1
    if not state.get('pipeline_id'):
        item=matches[0] if matches else definition_operation(base+'/dataPipelines',{'displayName':name,'description':'Historico ANP nacional: Copy binario parametrizado; arquivos preservados por tentativa','definition':definition})
        state['pipeline_id']=item['id'];write_json(binding,state)
    else:
        definition_operation(base+'/dataPipelines/'+state['pipeline_id']+'/updateDefinition',{'definition':definition})
    readback=definition_operation(base+'/dataPipelines/'+state['pipeline_id']+'/getDefinition')
    actual=json.loads(base64.b64decode(next(p for p in readback['definition']['parts'] if p['path']=='pipeline-content.json')['payload']))
    assert actual['properties']['activities']==payload['properties']['activities']
    assert actual['properties']['parameters']==payload['properties']['parameters']
    write_json(folder/'pipeline-readback.private.json',readback)
    print('Historical Copy pipeline prepared and read back; no job started',flush=True)
    raise SystemExit(0)

jobs=base+'/items/'+state['pipeline_id']+'/jobs'
if args.start:
    assert re.fullmatch('[a-z0-9_-]+',args.start)
    journal=folder/(args.start+'-accepted.json')
    assert not journal.exists(),'Tentativa ja registrada: acompanhar RunId existente'
    live=request('GET',jobs+'/instances').json()
    assert not live.get('continuationToken'),'Inspecionar paginacao antes de iniciar'
    assert all(j['status'] in {'Completed','Failed','Cancelled','Deduped'} for j in live['value']),'Pipeline ja ativo'
    pending=folder/(args.start+'-pending.json')
    assert not pending.exists(),'Submissao incerta: inspecionar historico antes de repetir'
    write_json(pending,{'attempt':args.start,'intent_at_utc':datetime.now(timezone.utc).isoformat()})
    response=request('POST',jobs+'/Pipeline/instances',{'executionData':{'pipelineName':name,'parameters':{'p_sources':sources}}})
    run_id=response.headers['Location'].rstrip('/').split('/')[-1]
    write_json(journal,{'run_id':run_id,'attempt':args.start,'accepted_at_utc':datetime.now(timezone.utc).isoformat(),'sources':sources})
    pending.unlink()
    print('Accepted historical pipeline',run_id,flush=True)
else:
    run_id=args.watch or args.verify
if args.verify:
    actual=request('GET',jobs+'/instances/'+run_id).json()
    assert actual['status']=='Completed',actual['status']
    fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id'])
    checks=[]
    for source in sources:
        path='landing/anp-history/'+source['source_id']+'/'+run_id+'/'+source['filename']
        content=fs.get_file_client(c['lakehouse_id']+'/Files/'+path).download_file().readall()
        sha=hashlib.sha256(content).hexdigest()
        assert len(content)==source['bytes'] and sha==source['sha256'],source['source_id']
        checks.append({'source_id':source['source_id'],'landing_relative_path':path,'sha256':sha,'bytes':len(content)})
        print('Copied bytes verified',source['source_id'],flush=True)
    write_json(ROOT/'evidence/phase2/history'/('landing-'+run_id+'.json'),{'status':'official_historical_copy_verified','environment':'fabric','run_id':run_id,'checked_at_utc':datetime.now(timezone.utc).isoformat(),'sources':checks})
else:
    deadline=time.monotonic()+900
    while True:
        actual=request('GET',jobs+'/instances/'+run_id).json()
        write_json(folder/('job-'+run_id+'.json'),actual)
        print(json.dumps({'run_id':run_id,'status':actual['status'],'failure':actual.get('failureReason')}),flush=True)
        if actual['status'] in {'Completed','Failed','Cancelled','Deduped'}:break
        assert time.monotonic()<deadline,'Retomar este mesmo RunId'
        time.sleep(20)
