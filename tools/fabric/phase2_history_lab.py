"""Correcao de arquivo antigo completo em namespaces sinteticos isolados."""
import argparse,base64,copy,hashlib,json,re,time
from datetime import datetime,timedelta,timezone
from azure.storage.filedatalake import DataLakeServiceClient
from client import ROOT,request,definition_operation,credential
from warehouse import connect,results
from evidence import write_json
from phase2_fingerprint import publication_fingerprint

p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
g.add_argument('--prepare',action='store_true');g.add_argument('--start',metavar='ATTEMPT');g.add_argument('--watch',metavar='RUN_ID');g.add_argument('--verify',metavar='RUN_ID');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/phase2-history';binding=folder/'lab-binding.json'
s=json.loads(binding.read_text()) if binding.exists() else {};bundles=json.loads((folder/'lab-bundles.json').read_text());official=json.loads((folder/'binding.json').read_text())
base=f"workspaces/{c['workspace_id']}";name='pl_hist_old_correction_lab'
def exp(value):return {'value':value,'type':'Expression'}
def dep(name):return [{'activity':name,'dependencyConditions':['Succeeded']}]
if args.prepare:
    workspace=request('GET',base).json();cap=next(x for x in request('GET','capacities').json()['value'] if x['id']==workspace['capacityId'])
    assert cap['sku'].startswith('FTL') and cap['state']=='Active'
    fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id'])
    def upload(relative,content):
        assert relative.startswith(('lab/history-correction/','shared_rules/'))
        prefix=c['lakehouse_id']+'/Files/'+relative;fs.get_directory_client(prefix.rsplit('/',1)[0]).create_directory();file=fs.get_file_client(prefix)
        if not file.exists():
            file.create_file()
            for offset in range(0,len(content),4*1024*1024):
                chunk=content[offset:offset+4*1024*1024];file.append_data(chunk,offset=offset,length=len(chunk))
            file.flush_data(len(content))
        assert hashlib.sha256(file.download_file().readall()).hexdigest()==hashlib.sha256(content).hexdigest()
    for kind in ['versions','publication']:
        bundle=bundles[kind]
        for path in sorted((ROOT/bundle['folder']).iterdir()):
            upload(bundle['relative_path']+'/'+path.name,path.read_bytes())
        rules=(ROOT/bundle['folder']/'rules.zip').read_bytes();upload('shared_rules/'+hashlib.sha256(rules).hexdigest()+'/fuelwatch_history_rules.zip',rules)
        nb=json.loads((ROOT/'notebooks'/(bundle['notebook_name']+'.ipynb')).read_text(encoding='utf8'))
        nb['metadata']['dependencies']={'lakehouse':{'default_lakehouse':c['lakehouse_id'],'default_lakehouse_name':'lh_fuelwatch','default_lakehouse_workspace_id':c['workspace_id'],'known_lakehouses':[{'id':c['lakehouse_id']}]}}
        definition={'format':'ipynb','parts':[{'path':'notebook-content.ipynb','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(nb,ensure_ascii=False).encode()).decode()}]}
        key=kind+'_notebook_id'
        if key not in s:
            matches=[x for x in request('GET',base+'/items').json()['value'] if x['displayName']==bundle['notebook_name']];assert len(matches)<=1
            item=matches[0] if matches else definition_operation(base+'/notebooks',{'displayName':bundle['notebook_name'],'description':'LAB sintetico isolado: republicacao antiga completa; mesmos motores oficiais','definition':definition})
            s[key]=item['id'];write_json(binding,s)
        else:definition_operation(base+'/notebooks/'+s[key]+'/updateDefinition',{'definition':definition})
        actual=definition_operation(base+'/notebooks/'+s[key]+'/getDefinition?format=ipynb')
        actual_nb=json.loads(base64.b64decode(next(x for x in actual['definition']['parts'] if x['path'].endswith('.ipynb'))['payload']))
        assert [x['source'] for x in actual_nb['cells']]==[x['source'] for x in nb['cells']]
        print('Lab notebook/input read back',kind,flush=True)
    archive=bundles['archive'];content=(ROOT/archive['local_path']).read_bytes();assert hashlib.sha256(content).hexdigest()==archive['source_sha256'];upload(archive['relative_path'],content)
    template=definition_operation(base+'/dataPipelines/'+official['master_pipeline_id']+'/getDefinition')
    template=json.loads(base64.b64decode(next(x for x in template['definition']['parts'] if x['path']=='pipeline-content.json')['payload']))
    root_activities=template['properties']['activities'];copy_activity=copy.deepcopy(root_activities[0]['typeProperties']['activities'][0])
    copy_activity['name']='Copy_Lab_Old_Correction';copy_activity['dependsOn']=[]
    sink=copy_activity['typeProperties']['sink']['datasetSettings']
    copy_activity['typeProperties']['source']={'type':'BinarySource','storeSettings':{'type':'LakehouseReadSettings','recursive':False},'formatSettings':{'type':'BinaryReadSettings'},'datasetSettings':{'annotations':[],'linkedService':copy.deepcopy(sink['linkedService']),'type':'Binary','typeProperties':{'location':{'type':'LakehouseLocation','folderPath':archive['relative_path'].rsplit('/',1)[0],'fileName':'lab_ca_2024_01.zip'}}}}
    sink['typeProperties']['location']={'type':'LakehouseLocation','folderPath':exp("@concat('lab/history-correction/landing/anp-history/anp_2024_1/',pipeline().RunId)"),'fileName':'lab_ca_2024_01.zip'}
    validation=copy.deepcopy(root_activities[1]);validation['dependsOn']=dep(copy_activity['name'])
    validation['typeProperties'].update(notebookId=s['versions_notebook_id'],sessionTag='fuelwatch_old_correction_lab',parameters={k:{'value':v,'type':'string'} for k,v in {'p_mode':'lab','p_bundle_relative_path':bundles['versions']['relative_path'],'p_manifest_sha256':bundles['versions']['manifest_sha256'],'p_landing_run_id':exp('@pipeline().RunId')}.items()})
    original_steps=root_activities[3]['typeProperties']['ifTrueActivities'];candidate=copy.deepcopy(original_steps[0]);candidate['dependsOn']=dep('Validate_Versions')
    candidate['typeProperties'].update(notebookId=s['publication_notebook_id'],sessionTag='fuelwatch_old_correction_lab',parameters={k:{'value':v,'type':'string'} for k,v in {'p_mode':'lab','p_bundle_relative_path':bundles['publication']['relative_path'],'p_manifest_sha256':bundles['publication']['manifest_sha256'],'p_fault_stage':'none'}.items()})
    def sql_step(label,text,after,retry=0):
        a=copy.deepcopy(original_steps[1]);a['name']=label;a['dependsOn']=dep(after);a['policy']['retry']=retry
        a['typeProperties']['scripts']=[{'type':'Query','text':text}];return a
    gate=(ROOT/'sql/history/lab/05_visibility_gate.sql').read_text(encoding='utf8');before,after=gate.split('{{BATCH_ID}}')
    visible=sql_step('Wait_Exact_SQL_Visibility',exp("@concat('"+before.replace("'","''")+"',json(activity('Build_Candidate').output.result.exitValue).run_id,'"+after.replace("'","''")+"')"),'Build_Candidate',12)
    install_gold=sql_step('Install_Lab_Gold_Procedure',(ROOT/'sql/history/lab/03_publish.sql').read_text(encoding='utf8'),'Wait_Exact_SQL_Visibility')
    install_stage=sql_step('Install_Lab_Stage_Procedure',(ROOT/'sql/history/lab/04_stage_and_publish.sql').read_text(encoding='utf8'),'Install_Lab_Gold_Procedure')
    publish=sql_step('Publish_Corrected_Lab_Gold',exp("@concat('EXEC lab_gold_hist.stage_and_publish @batch_id=''',json(activity('Build_Candidate').output.result.exitValue).run_id,''',@snapshot_sha256=''',pipeline().parameters.p_publication_sha,''';')"),'Install_Lab_Stage_Procedure')
    content={'properties':{'activities':[copy_activity,validation,candidate,visible,install_gold,install_stage,publish],'parameters':{'p_publication_sha':{'type':'string','defaultValue':bundles['publication']['manifest_sha256']}}}}
    definition={'parts':[{'path':'pipeline-content.json','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(content).encode()).decode()}]}
    if not s.get('pipeline_id'):
        matches=[x for x in request('GET',base+'/items').json()['value'] if x['displayName']==name];assert len(matches)<=1
        item=matches[0] if matches else definition_operation(base+'/dataPipelines',{'displayName':name,'description':'LAB sintetico: arquivo antigo completo, 2.125.547 coletas; nunca publica no oficial','definition':definition});s['pipeline_id']=item['id'];write_json(binding,s)
    else:definition_operation(base+'/dataPipelines/'+s['pipeline_id']+'/updateDefinition',{'definition':definition})
    actual=definition_operation(base+'/dataPipelines/'+s['pipeline_id']+'/getDefinition');actual=json.loads(base64.b64decode(next(x for x in actual['definition']['parts'] if x['path']=='pipeline-content.json')['payload']))
    assert actual['properties']['activities']==content['properties']['activities'];write_json(folder/'lab-pipeline-readback.private.json',actual)
    with connect(c) as cn:
        for text in re.split(r'(?m)^GO\s*$',(ROOT/'sql/history/lab/01_schema.sql').read_text(encoding='utf8')):
            if text.strip():results(cn.cursor().execute(text))
        for statement in (ROOT/'sql/history/lab/02_views.sql').read_text(encoding='utf8').split('CREATE OR ALTER VIEW ')[1:]:results(cn.cursor().execute('CREATE OR ALTER VIEW '+statement))
    print('Full old-file correction lab prepared; no job started',flush=True);raise SystemExit(0)
jobs=base+'/items/'+s['pipeline_id']+'/jobs'
if args.start:
    assert re.fullmatch('[a-z0-9_-]+',args.start)
    journal=folder/(args.start+'-lab-accepted.json');pending=folder/(args.start+'-lab-pending.json');assert not journal.exists() and not pending.exists()
    for item in request('GET',base+'/items').json()['value']:
        if item['type']=='DataPipeline':
            assert not any(x['enabled'] for x in request('GET',base+'/items/'+item['id']+'/jobs/Pipeline/schedules').json()['value']),'Agenda ativa: concluir antes do laboratorio'
            assert all(j['status'] in ['Completed','Failed','Cancelled','Deduped'] for j in request('GET',base+'/items/'+item['id']+'/jobs/instances').json()['value']),'Pipeline ativo'
        elif item['type']=='Notebook':
            assert all(x['state'] in ['Succeeded','Failed','Cancelled','Dead','Error','Success'] for x in request('GET',base+'/notebooks/'+item['id']+'/livySessions').json()['value']),'Sessao Spark ativa'
    with connect(c) as cn:
        cn.timeout=900;cur=cn.cursor();before=publication_fingerprint(cur)
        write_json(folder/'lab-official-baseline.json',before)
        assert cur.execute('SELECT COUNT_BIG(*) FROM lab_gold_hist.fato_preco_coletado').fetchone()[0]==0,'Inspecionar baseline lab ja existente'
        print('Seeding isolated complete historical lab baseline',flush=True)
        seed='BEGIN TRY BEGIN TRANSACTION;\n'
        for table in ['dim_data','dim_municipio','dim_produto','dim_posto','fato_preco_coletado','source_versions']:
            seed+='INSERT INTO lab_gold_hist.'+table+' SELECT * FROM gold_hist.'+table+';\n'
        seed+="INSERT INTO lab_gold_hist.publication SELECT batch_id,'lab-baseline-copy',source_sha256,ibge_sha256,silver_delta_version,CAST(1 AS bit),published_at_utc,rows_published,source_table,snapshot_id FROM gold_hist.publication; COMMIT TRANSACTION; END TRY BEGIN CATCH IF @@TRANCOUNT>0 ROLLBACK TRANSACTION; THROW; END CATCH;"
        results(cur.execute(seed))
    write_json(pending,{'intent_at_utc':datetime.now(timezone.utc).isoformat()})
    response=request('POST',jobs+'/Pipeline/instances',{'executionData':{'pipelineName':name,'parameters':{}}});run=response.headers['Location'].rstrip('/').split('/')[-1]
    write_json(journal,{'run_id':run,'is_synthetic':True,'accepted_at_utc':datetime.now(timezone.utc).isoformat()});pending.unlink();print('Accepted full old-correction lab',run,flush=True)
else:run=args.watch or args.verify
if args.verify:
    job=request('GET',jobs+'/instances/'+run).json();assert job['status']=='Completed',job
    now=datetime.now(timezone.utc)
    activity_response=request('POST',base+'/datapipelines/pipelineruns/'+run+'/queryactivityruns',{'filters':[],'orderBy':[{'orderBy':'ActivityRunStart','order':'ASC'}],'lastUpdatedAfter':(now-timedelta(days=2)).isoformat(),'lastUpdatedBefore':(now+timedelta(minutes=1)).isoformat()}).json()
    assert not isinstance(activity_response,dict) or not activity_response.get('continuationToken')
    activities=activity_response.get('value',[]) if isinstance(activity_response,dict) else activity_response
    by_name={a['activityName']:a for a in activities}
    for name in ['Copy_Lab_Old_Correction','Validate_Versions','Build_Candidate','Wait_Exact_SQL_Visibility','Install_Lab_Gold_Procedure','Install_Lab_Stage_Procedure','Publish_Corrected_Lab_Gold']:
        assert by_name[name]['status']=='Succeeded',(name,by_name[name]['status'])
    versions_receipt=json.loads(by_name['Validate_Versions']['output']['result']['exitValue'])
    candidate_receipt=json.loads(by_name['Build_Candidate']['output']['result']['exitValue'])
    assert versions_receipt['is_synthetic'] and candidate_receipt['is_synthetic'] and candidate_receipt['full_business_comparison_passed']
    with connect(c) as cn:
        cn.timeout=900;cur=cn.cursor();after=publication_fingerprint(cur);before=json.loads((folder/'lab-official-baseline.json').read_text());assert before==after,'Laboratorio alterou publicacao oficial'
        expected=json.loads((ROOT/'evidence/phase2/history/lab/publication-reference.json').read_text(encoding='utf8'));fixture=json.loads((ROOT/'evidence/phase2/history/lab/fixture.json').read_text(encoding='utf8'))
        count=cur.execute('SELECT COUNT_BIG(*) FROM lab_gold_hist.business_published').fetchone()[0];assert count==expected['rows']
        assert cur.execute('SELECT COUNT_BIG(*) FROM lab_gold_hist.dim_posto').fetchone()[0]==expected['station_versions']
        price=cur.execute('SELECT preco_venda FROM lab_gold_hist.business_published WHERE cnpj=? AND data_coleta=? AND produto=?',fixture['target']['cnpj'],fixture['target']['data_coleta'],fixture['target']['produto']).fetchone()[0]
        assert str(price)==fixture['target']['new_price']
        pub=results(cur.execute('SELECT * FROM lab_gold_hist.publication'))[0];assert len(pub)==1 and pub[0]['is_synthetic']
        assert pub[0]['batch_id']==candidate_receipt['run_id'] and pub[0]['source_sha256']==bundles['publication']['manifest_sha256']
        versions=results(cur.execute("SELECT source_sha256,COUNT_BIG(*) AS rows FROM lh_fuelwatch.dbo.lab_hist_silver_versoes WHERE source_id='anp_2024_1' GROUP BY source_sha256"))[0]
        assert {v['source_sha256'] for v in versions}=={fixture['original_source_sha256'],fixture['corrected_source_sha256']}
    write_json(ROOT/'evidence/phase2/history/lab/fabric-correction.json',{'status':'full_old_file_correction_validated_in_fabric','is_synthetic':True,'pipeline_run_id':run,'rows':count,'station_versions':expected['station_versions'],'target_price':str(price),'both_source_versions_preserved':versions,'versions_receipt':versions_receipt,'candidate_receipt':candidate_receipt,'activities':[{k:a.get(k) for k in ['activityName','status','durationInMs']} for a in activities],'official_before':before,'official_after':after,'publication':pub,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
    print('Full historical old-file correction verified; official data unchanged',flush=True)
else:
    deadline=time.monotonic()+3600
    while True:
        job=request('GET',jobs+'/instances/'+run).json();write_json(folder/('lab-job-'+run+'.json'),job)
        print(json.dumps({'run_id':run,'status':job['status'],'failure':job.get('failureReason')}),flush=True)
        if job['status'] in ['Completed','Failed','Cancelled','Deduped']:break
        assert time.monotonic()<deadline,'Retomar mesmo run_id';time.sleep(30)
