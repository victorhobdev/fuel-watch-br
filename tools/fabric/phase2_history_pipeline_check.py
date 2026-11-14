"""Conferir atividades reais, run exato e publicacao do pipeline historico."""
import argparse,json
from datetime import datetime,timedelta,timezone
from client import ROOT,request
from warehouse import connect,results
from evidence import write_json
p=argparse.ArgumentParser();p.add_argument('run_id');p.add_argument('--expect-skipped',action='store_true');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/phase2-history';s=json.loads((folder/'binding.json').read_text());base=f"workspaces/{c['workspace_id']}"
job=request('GET',base+'/items/'+s['master_pipeline_id']+'/jobs/instances/'+args.run_id).json();assert job['status']=='Completed',job['status']
now=datetime.now(timezone.utc)
body={'filters':[],'orderBy':[{'orderBy':'ActivityRunStart','order':'ASC'}],'lastUpdatedAfter':(now-timedelta(days=2)).isoformat(),'lastUpdatedBefore':(now+timedelta(minutes=1)).isoformat()}
response=request('POST',base+'/datapipelines/pipelineruns/'+args.run_id+'/queryactivityruns',body).json()
assert not isinstance(response,dict) or not response.get('continuationToken'),'Inspecionar todas as atividades'
activities=response.get('value',[]) if isinstance(response,dict) else response
by_name={a['activityName']:a for a in activities}
for name in ['For_Each_Official_Version','Validate_Versions','Check_Current_Publication','Publish_When_Required']:
    assert by_name[name]['status']=='Succeeded',(name,by_name[name]['status'])
copies=[a for a in activities if a['activityName']=='Copy_Official_Version']
profiles=json.loads((ROOT/'evidence/phase2/history/profile-summary.json').read_text(encoding='utf8'))['profiles']
assert len(copies)==len(profiles) and all(a['status']=='Succeeded' for a in copies)
assert sum(a['output']['dataWritten'] for a in copies)==sum(s['source_bytes'] for s in profiles)
versions=json.loads(by_name['Validate_Versions']['output']['result']['exitValue'])
assert versions['status']=='historical_versions_silver_validated'
with connect(c) as cn:
    cn.timeout=900
    publication=results(cn.cursor().execute('SELECT * FROM gold_hist.publication'))[0];assert len(publication)==1
    totals=results(cn.cursor().execute('SELECT COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos,COUNT(DISTINCT municipio_ibge) AS municipios FROM gold_hist.business_published'))[0][0]
    expected=json.loads((ROOT/'evidence/phase2/history/publication-reference.json').read_text(encoding='utf8'))
    assert totals=={'coletas':expected['rows'],'postos':expected['stations'],'municipios':expected['municipalities']}
    if args.expect_skipped:
        accepted=[json.loads(p.read_text(encoding='utf8')) for p in folder.glob('*-master-accepted.json')]
        accepted=next(a for a in accepted if a['run_id']==args.run_id)
        assert json.loads(json.dumps(publication,default=str))==accepted['publication_before'],'Repeticao mudou a publicacao'
        assert versions['all_versions_reused'] is True
        assert by_name['Identical_Publication_Skipped']['status']=='Succeeded'
        assert all(name not in by_name for name in ['Build_Candidate','Publish_Protected_Gold'])
    else:
        for name in ['Build_Candidate','Wait_Exact_SQL_Visibility','Install_Stage_Procedure','Publish_Protected_Gold','Verify_Exact_Publication']:
            assert by_name[name]['status']=='Succeeded',(name,by_name[name]['status'])
        candidate=json.loads(by_name['Build_Candidate']['output']['result']['exitValue'])
        assert candidate['status']=='historical_publication_candidate_validated' and candidate['full_business_comparison_passed']
        assert publication[0]['batch_id']==candidate['run_id']
        assert publication[0]['source_sha256']==candidate['manifest_sha256']
report={'status':'historical_integrated_skip_verified' if args.expect_skipped else 'historical_integrated_end_to_end_verified','environment':'fabric','pipeline_run_id':args.run_id,'job_start':job['startTimeUtc'],'job_end':job['endTimeUtc'],'activities':[{'name':a['activityName'],'status':a['status'],'duration_ms':a.get('durationInMs'),'bytes_read':a.get('output',{}).get('dataRead'),'bytes_written':a.get('output',{}).get('dataWritten'),'execution_seconds':a.get('output',{}).get('executionDuration')} for a in activities],'versions_receipt':versions,'publication':publication,'totals':totals,'checked_at_utc':datetime.now(timezone.utc).isoformat()}
write_json(ROOT/'evidence/phase2/refresh'/('pipeline-'+args.run_id+'.json'),report)
print(json.dumps({'status':report['status'],'run_id':args.run_id,'totals':totals}),flush=True)
