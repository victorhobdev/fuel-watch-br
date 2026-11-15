"""Prepara regra histórica desligada e ação interna de auditoria isolada."""
import base64
import copy
import json
from uuid import uuid4
from client import ROOT,request,definition_operation
from warehouse import connect,results
from evidence import write_json

c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
legacy=json.loads((ROOT/'.local/m10-api/binding.json').read_text())
m=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
folder=ROOT/'.local/phase2-streaming'
binding=folder/'binding.json'
state=json.loads(binding.read_text()) if binding.exists() else {'lab_run_id':m['lab_run_id']}
assert state['lab_run_id']==m['lab_run_id']
w=c['workspace_id']
with connect() as cn:
 results(cn.cursor().execute("IF SCHEMA_ID('lab_f2') IS NULL EXEC('CREATE SCHEMA lab_f2'); IF OBJECT_ID('lab_f2.alert_audit') IS NULL CREATE TABLE lab_f2.alert_audit (pipeline_run_id varchar(36),lab_run_id varchar(36),benchmark_version varchar(64),recorded_at_utc datetime2(6),is_synthetic bit);"))
if not state.get('alert_pipeline_id'):
 parent=definition_operation(f"workspaces/{w}/dataPipelines/{legacy['alert_pipeline_id']}/getDefinition")
 content=json.loads(base64.b64decode(next(p for p in parent['definition']['parts'] if p['path']=='pipeline-content.json')['payload']))
 activity=content['properties']['activities'][0]
 activity['typeProperties']['scripts']=[{'type':'Query','text':{'type':'Expression','value':"@concat('INSERT INTO lab_f2.alert_audit VALUES (''',pipeline().RunId,''',''"+m['lab_run_id']+"'',''"+m['benchmark']['benchmark_version']+"'',CAST(SYSUTCDATETIME() AS datetime2(6)),1);')"}}]
 name='pl_f2_historical_alert_audit'
 matches=[x for x in request('GET',f'workspaces/{w}/items').json()['value'] if x['displayName']==name]
 assert len(matches)<=1
 if matches:
  state['alert_pipeline_id']=matches[0]['id']
 else:
  part={'path':'pipeline-content.json','payloadType':'InlineBase64','payload':base64.b64encode(json.dumps(content).encode()).decode()}
  item=definition_operation(f'workspaces/{w}/dataPipelines',{'displayName':name,'description':'Synthetic historical alert audit; no external notification','definition':{'parts':[part]}})
  state['alert_pipeline_id']=item['id']
 write_json(binding,state)
base=f"workspaces/{w}/reflexes/{legacy['activator']['id']}"
definition=definition_operation(base+'/getDefinition')
write_json(folder/'rule-before.private.json',definition)
part=next(p for p in definition['definition']['parts'] if p['path']=='ReflexEntities.json')
entities=json.loads(base64.b64decode(part['payload']))
old=next(e for e in entities if e['uniqueIdentifier']==legacy['activator']['rule_id'])
assert old['payload']['definition']['settings']['shouldRun'] is False
if not state.get('rule_id'):
 assert not any(e.get('payload',{}).get('name')=='Historical benchmark alert' for e in entities),'Inspecionar regra existente antes de duplicar'
 rule=copy.deepcopy(old)
 rule['uniqueIdentifier']=str(uuid4())
 rule['payload']['name']='Historical benchmark alert'
 rule['payload']['description']='Versioned synthetic benchmark; alert_score classification independently reconciled in KQL'
 instance=json.loads(rule['payload']['definition']['instance'])
 instance['templateVersion']='1.3.1'
 action_id=str(uuid4())
 for step in instance['steps']:
  step['id']=str(uuid4())
  if step['name']=='EventDetectStep':
   step['rows'].append({'name':'OccurrenceOption','kind':'EachTime','arguments':[]})
  for row in step['rows']:
   if row['name']=='EventFieldSelector':row['arguments'][0]['value']='alert_score'
   if row['name']=='NumberBecomes':
    next(a for a in row['arguments'] if a['name']=='value')['value']=0.5
   if row['name']=='FabricItemBinding':
    for arg in row['arguments']:
     if arg['name']=='itemId':arg['value']=state['alert_pipeline_id']
     if arg['name']=='fabricJobConnectionDocumentId':arg['value']=action_id
 rule['payload']['definition']['instance']=json.dumps(instance)
 rule['payload']['definition']['settings']['shouldRun']=False
 entities.extend([{'uniqueIdentifier':action_id,'type':'fabricItemAction-v1','payload':{'name':'Audit historical synthetic alert','fabricItem':{'itemId':state['alert_pipeline_id'],'workspaceId':w,'itemType':'Pipeline'},'jobType':'Pipeline'}},rule])
 part['payload']=base64.b64encode(json.dumps(entities).encode()).decode()
 definition['definition'].pop('format',None)
 definition_operation(base+'/updateDefinition',{'definition':definition['definition']})
 state['rule_id']=rule['uniqueIdentifier']
 write_json(binding,state)
actual=definition_operation(base+'/getDefinition')
found=json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path']=='ReflexEntities.json')['payload']))
rule=next(e for e in found if e['uniqueIdentifier']==state['rule_id'])
assert rule['payload']['definition']['settings']['shouldRun'] is False
assert 'alert_score' in rule['payload']['definition']['instance']
write_json(ROOT/'evidence/phase2/streaming/rule-prepared.json',{'status':'historical_rule_prepared_disabled','environment':'fabric','lab_run_id':m['lab_run_id'],'benchmark_version':m['benchmark']['benchmark_version'],'rule_id':state['rule_id'],'action_pipeline_id':state['alert_pipeline_id'],'runtime_trigger_verified':False})
print('Regra histórica e ação de auditoria conferidas; regra desligada',flush=True)
