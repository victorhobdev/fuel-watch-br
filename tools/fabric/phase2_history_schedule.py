"""Uma agenda Fabric em janela finita; desabilitar antes de acompanhar o job."""
import argparse,json,subprocess,sys,time
from datetime import datetime,timedelta,timezone
from client import ROOT,request
from warehouse import connect,results
from evidence import write_json
p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());folder=ROOT/'.local/phase2-history';binding=json.loads((folder/'binding.json').read_text())
base=f"workspaces/{c['workspace_id']}/items/{binding['master_pipeline_id']}/jobs";journal=folder/'master-schedule-once.json'
if args.resume:
    report=json.loads(journal.read_text());assert report.get('schedule_id'),'Inspecionar criacao incerta; nao reenviar POST'
else:
    assert not journal.exists(),'Retomar agenda existente com --resume'
    proofs=[json.loads(p.read_text(encoding='utf8')) for p in (ROOT/'evidence/phase2/refresh').glob('pipeline-*.json')]
    assert any(p['status']=='historical_integrated_end_to_end_verified' for p in proofs)
    assert any(p['status']=='historical_integrated_skip_verified' for p in proofs)
    jobs=request('GET',base+'/instances').json();assert not jobs.get('continuationToken')
    assert all(j['status'] in ['Completed','Failed','Cancelled','Deduped'] for j in jobs['value'])
    assert not any(s['enabled'] for s in request('GET',base+'/Pipeline/schedules').json()['value'])
    start=datetime.now(timezone.utc)+timedelta(minutes=2);end=start+timedelta(minutes=5)
    body={'enabled':True,'configuration':{'startDateTime':start.strftime('%Y-%m-%dT%H:%M:%SZ'),'endDateTime':end.strftime('%Y-%m-%dT%H:%M:%SZ'),'localTimeZoneId':'UTC','type':'Cron','interval':60},'executionData':{'pipelineName':'pl_fuelwatch_historico','parameters':{'p_force_rebuild':False}}}
    with connect(c) as cn:before=results(cn.cursor().execute('SELECT * FROM gold_hist.publication'))[0]
    report={'status':'creating','request':body,'previous_job_ids':[j['id'] for j in jobs['value']],'publication_before':before}
    write_json(journal,report)
    response=request('POST',base+'/Pipeline/schedules',body).json();report.update(status='scheduled',schedule_id=response['id']);write_json(journal,report)
schedule_path=base+'/Pipeline/schedules/'+report['schedule_id'];job_id=report.get('job_id')
try:
    end=datetime.fromisoformat(report['request']['configuration']['endDateTime'].replace('Z','+00:00'))
    while job_id is None and datetime.now(timezone.utc)<end+timedelta(minutes=3):
        jobs=request('GET',base+'/instances').json()['value'];added=[j for j in jobs if j['id'] not in report['previous_job_ids']]
        if added:
            assert len(added)==1 and added[0]['invokeType']=='Scheduled',added
            job_id=added[0]['id'];report.update(status='triggered',job_id=job_id,invoke_type=added[0]['invokeType']);write_json(journal,report)
            write_json(folder/'scheduled-once-master-accepted.json',{'run_id':job_id,'force_rebuild':False,'publication_before':report['publication_before']})
            break
        print('Waiting for finite scheduled historical run',report['schedule_id'],flush=True);time.sleep(30)
    assert job_id,'Disparo nao observado; consultar historico antes de outra agenda'
finally:
    request('PATCH',schedule_path,{**report['request'],'enabled':False})
    actual=request('GET',schedule_path).json();assert actual['enabled'] is False
    report['disabled_verified']=True;write_json(journal,report)
print('Schedule disabled; observing accepted job',job_id,flush=True)
subprocess.run([sys.executable,str(ROOT/'tools/fabric/phase2_history_pipeline.py'),'--watch',job_id],check=True)
subprocess.run([sys.executable,str(ROOT/'tools/fabric/phase2_history_pipeline_check.py'),job_id,'--expect-skipped'],check=True)
assert not any(s['enabled'] for s in request('GET',base+'/Pipeline/schedules').json()['value'])
report['status']='historical_scheduled_run_verified_and_disabled';write_json(journal,report)
write_json(ROOT/'evidence/phase2/refresh/schedule-once.json',report)
print(report['status'],flush=True)
