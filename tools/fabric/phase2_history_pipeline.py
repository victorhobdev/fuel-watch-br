"""Orquestracao Fabric: Copy -> versoes -> candidato -> visibilidade -> Gold."""
import argparse,base64,copy,json,re,time
from datetime import datetime,timedelta,timezone
from client import ROOT,request,definition_operation
from evidence import write_json
from warehouse import connect,results

p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
g.add_argument('--prepare',action='store_true');g.add_argument('--start',metavar='ATTEMPT');g.add_argument('--watch',metavar='RUN_ID')
p.add_argument('--force-rebuild',action='store_true');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/phase2-history';binding=folder/'binding.json';s=json.loads(binding.read_text())
base=f"workspaces/{c['workspace_id']}";name='pl_fuelwatch_historico'
versions=json.loads((folder/'bundle.json').read_text());publication=json.loads((folder/'publication-bundle.json').read_text())

def expr(value):return {'value':value,'type':'Expression'}
def depends(name):return [{'activity':name,'dependencyConditions':['Succeeded']}] if name else []
policy={'timeout':'0.01:00:00','retry':0,'retryIntervalInSeconds':30,'secureOutput':False,'secureInput':False}
def notebook(label,item,parameters,after):
    return {'name':label,'type':'TridentNotebook','dependsOn':depends(after),'policy':copy.deepcopy(policy),
        'typeProperties':{'notebookId':item,'workspaceId':c['workspace_id'],'sessionTag':'fuelwatch_history_serial',
            'parameters':{key:{'value':value,'type':'string'} for key,value in parameters.items()}}}

if args.prepare:
    workspace=request('GET',base).json();cap=next(x for x in request('GET','capacities').json()['value'] if x['id']==workspace['capacityId'])
    assert cap['sku'].startswith('FTL') and cap['state']=='Active'
    source=definition_operation(base+'/dataPipelines/'+s['pipeline_id']+'/getDefinition')
    source=json.loads(base64.b64decode(next(x for x in source['definition']['parts'] if x['path']=='pipeline-content.json')['payload']))
    loop=copy.deepcopy(source['properties']['activities'][0]);assert loop['type']=='ForEach'
    parent=definition_operation(base+'/dataPipelines/'+c['pipeline_id']+'/getDefinition')
    parent=json.loads(base64.b64decode(next(x for x in parent['definition']['parts'] if x['path']=='pipeline-content.json')['payload']))
    sql_template=next(a for a in parent['properties']['activities'] if a['type']=='Script')
    def script(label,text,after=None,retries=0):
        a=copy.deepcopy(sql_template);a['name']=label;a['dependsOn']=depends(after);a['policy']=copy.deepcopy(policy);a['policy']['retry']=retries
        a['typeProperties']={'scripts':[{'type':'Query','text':text}],'scriptBlockExecutionTimeout':'00:30:00'}
        return a
    validation=notebook('Validate_Versions',s['notebook_id'],{'p_landing_run_id':expr('@pipeline().RunId'),'p_bundle_relative_path':expr('@pipeline().parameters.p_versions_path'),'p_manifest_sha256':expr('@pipeline().parameters.p_versions_sha')},loop['name'])
    current=script('Check_Current_Publication',expr("@concat('SELECT COUNT_BIG(*) AS current_publication FROM gold_hist.publication WHERE source_sha256=''',pipeline().parameters.p_publication_sha,''';')"),'Validate_Versions')
    candidate=notebook('Build_Candidate',s['publication_notebook_id'],{'p_bundle_relative_path':expr('@pipeline().parameters.p_publication_path'),'p_manifest_sha256':expr('@pipeline().parameters.p_publication_sha'),'p_fault_stage':'none'},None)
    gate=(ROOT/'sql/history/05_visibility_gate.sql').read_text(encoding='utf8')
    # Concat insere somente UUID devolvido pelo notebook; literais SQL sao escapados.
    before,after=gate.split('{{BATCH_ID}}')
    gate_expr=expr("@concat('"+before.replace("'","''")+"',json(activity('Build_Candidate').output.result.exitValue).run_id,'"+after.replace("'","''")+"')")
    visible=script('Wait_Exact_SQL_Visibility',gate_expr,'Build_Candidate',retries=12)
    install=script('Install_Stage_Procedure',(ROOT/'sql/history/04_stage_and_publish.sql').read_text(encoding='utf8'),'Wait_Exact_SQL_Visibility')
    publish=script('Publish_Protected_Gold',expr("@concat('EXEC gold_hist.stage_and_publish @batch_id=''',json(activity('Build_Candidate').output.result.exitValue).run_id,''',@snapshot_sha256=''',pipeline().parameters.p_publication_sha,''',@expected_previous_batch_id=''',pipeline().parameters.p_expected_previous_batch_id,''';')"),'Install_Stage_Procedure')
    verify=script('Verify_Exact_Publication',expr("@concat('IF (SELECT COUNT_BIG(*) FROM gold_hist.publication WHERE batch_id=''',json(activity('Build_Candidate').output.result.exitValue).run_id,''' AND source_sha256=''',pipeline().parameters.p_publication_sha,''')<>1 THROW 51846,''Publicacao nao corresponde ao run exato.'',1; SELECT ''historical_pipeline_published'' AS status;')"),'Publish_Protected_Gold')
    changed={'name':'Publish_When_Required','type':'IfCondition','dependsOn':depends('Check_Current_Publication'),'typeProperties':{
        'expression':expr("@or(pipeline().parameters.p_force_rebuild,or(not(json(activity('Validate_Versions').output.result.exitValue).all_versions_reused),equals(activity('Check_Current_Publication').output.resultSets[0].rows[0].current_publication,0)))"),
        'ifTrueActivities':[candidate,visible,install,publish,verify],
        'ifFalseActivities':[{'name':'Identical_Publication_Skipped','type':'Wait','dependsOn':[],'typeProperties':{'waitTimeInSeconds':1}}]}}
    parameters=copy.deepcopy(source['properties']['parameters'])
    parameters.update({key:{'type':'string','defaultValue':value} for key,value in {'p_versions_path':versions['relative_path'],'p_versions_sha':versions['manifest_sha256'],'p_publication_path':publication['relative_path'],'p_publication_sha':publication['manifest_sha256'],'p_expected_previous_batch_id':''}.items()})
    parameters['p_force_rebuild']={'type':'bool','defaultValue':False}
    content={'properties':{'activities':[loop,validation,current,changed],'parameters':parameters}}
    definition={'parts':[{'path':'pipeline-content.json','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(content).encode()).decode()}]}
    matches=[x for x in request('GET',base+'/items').json()['value'] if x['displayName']==name];assert len(matches)<=1
    if not s.get('master_pipeline_id'):
        item=matches[0] if matches else definition_operation(base+'/dataPipelines',{'displayName':name,'description':'Historico nacional integrado; aprovacao por manifesto e publicacao transacional','definition':definition})
        s['master_pipeline_id']=item['id'];write_json(binding,s)
    else:definition_operation(base+'/dataPipelines/'+s['master_pipeline_id']+'/updateDefinition',{'definition':definition})
    actual=definition_operation(base+'/dataPipelines/'+s['master_pipeline_id']+'/getDefinition')
    actual_content=json.loads(base64.b64decode(next(x for x in actual['definition']['parts'] if x['path']=='pipeline-content.json')['payload']))
    assert actual_content['properties']['activities']==content['properties']['activities']
    write_json(folder/'master-pipeline-readback.private.json',actual)
    print('Integrated historical pipeline prepared and read back; no job started',flush=True)
    raise SystemExit(0)
jobs=base+'/items/'+s['master_pipeline_id']+'/jobs'
if args.start:
    assert re.fullmatch('[a-z0-9_-]+',args.start)
    accepted=folder/(args.start+'-master-accepted.json');pending=folder/(args.start+'-master-pending.json')
    assert not accepted.exists() and not pending.exists(),'Retomar tentativa registrada; nao duplicar'
    history=request('GET',jobs+'/instances').json();assert not history.get('continuationToken')
    assert all(j['status'] in {'Completed','Failed','Cancelled','Deduped'} for j in history['value']),'Pipeline ativo'
    for item in request('GET',base+'/items').json()['value']:
        if item['type']=='Notebook':
            sessions=request('GET',base+'/notebooks/'+item['id']+'/livySessions').json()['value']
            assert all(x['state'] in {'Succeeded','Failed','Cancelled','Dead','Error','Success'} for x in sessions),'Sessao Spark ativa'
    write_json(pending,{'intent_at_utc':datetime.now(timezone.utc).isoformat(),'force_rebuild':args.force_rebuild})
    with connect(c) as cn:publication_before=results(cn.cursor().execute('SELECT * FROM gold_hist.publication'))[0]
    assert len(publication_before)<=1,'Publicacao atual ambigua; interromper'
    expected_previous=publication_before[0]['batch_id'] if publication_before else ''
    response=request('POST',jobs+'/Pipeline/instances',{'executionData':{'pipelineName':name,'parameters':{'p_force_rebuild':args.force_rebuild,'p_expected_previous_batch_id':expected_previous}}})
    run=response.headers['Location'].rstrip('/').split('/')[-1]
    write_json(accepted,{'run_id':run,'force_rebuild':args.force_rebuild,'publication_before':publication_before,'accepted_at_utc':datetime.now(timezone.utc).isoformat()});pending.unlink()
    print('Accepted integrated pipeline',run,flush=True)
else:run=args.watch
deadline=time.monotonic()+3600
while True:
    job=request('GET',jobs+'/instances/'+run).json();write_json(folder/('master-job-'+run+'.json'),job)
    now=datetime.now(timezone.utc)
    activities=request('POST',base+'/datapipelines/pipelineruns/'+run+'/queryactivityruns',{'filters':[],'orderBy':[{'orderBy':'ActivityRunStart','order':'ASC'}],'lastUpdatedAfter':(now-timedelta(days=2)).isoformat(),'lastUpdatedBefore':(now+timedelta(minutes=1)).isoformat()}).json()
    write_json(folder/('master-activities-'+run+'.json'),activities)
    values=activities.get('value',[]) if isinstance(activities,dict) else activities
    print(json.dumps({'run_id':run,'status':job['status'],'activities':{x['activityName']:x['status'] for x in values}}),flush=True)
    if job['status'] in {'Completed','Failed','Cancelled','Deduped'}:break
    assert time.monotonic()<deadline,'Retomar este mesmo RunId'
    time.sleep(30)
