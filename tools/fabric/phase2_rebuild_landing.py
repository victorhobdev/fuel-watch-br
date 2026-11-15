"""Prepara Copy dos cinco arquivos oficiais com destino isolado de reconstrução."""
import base64,json
from datetime import datetime,timezone
from urllib.parse import urlparse
from client import ROOT,request,definition_operation
from evidence import write_json
folder=ROOT/'.local/phase2-rebuild';binding=folder/'binding.json';s=json.loads(binding.read_text())
dev=json.loads((ROOT/'.local/fabric-environment.json').read_text());history=json.loads((ROOT/'.local/phase2-history/binding.json').read_text())
assert s['workspace_id']!=dev['workspace_id']
original=definition_operation(f"workspaces/{dev['workspace_id']}/dataPipelines/{history['pipeline_id']}/getDefinition")
content=json.loads(base64.b64decode(next(p for p in original['definition']['parts'] if p['path']=='pipeline-content.json')['payload']))
text=json.dumps(content).replace(dev['workspace_id'],s['workspace_id']).replace(dev['lakehouse_id'],s['lakehouse']['id'])
content=json.loads(text)
sources=content['properties']['parameters']['p_sources']['defaultValue']
national=json.loads((ROOT/'data/artifacts/national/bundle/manifest.json').read_text())
# A fonte de 2026 usa os bytes aprovados, preservados no ledger local.
ledger=[json.loads(x) for x in (ROOT/'data/manifest/downloads.jsonl').read_text(encoding='utf8').splitlines()]
source=next(x for x in reversed(ledger) if x['source_id']=='anp_2026_1' and x['sha256']==national['anp']['sha256'])
url=source.get('url') or source.get('source_url')
assert url,'URL oficial ausente no ledger'
sources.append({'source_id':'anp_2026_1','relative_url':urlparse(url).path,'sha256':source['sha256'],'filename':'ca-2026-01.zip','bytes':source.get('bytes',source.get('size_bytes'))})
copy=content['properties']['activities'][0]['typeProperties']['activities'][0]
copy['typeProperties']['sink']['datasetSettings']['typeProperties']['location']['folderPath']={'value':"@if(equals(item().source_id,'anp_2026_1'),concat('landing/anp/2026-1/',pipeline().RunId),concat('landing/anp-history/',item().source_id,'/',pipeline().RunId))",'type':'Expression'}
encoded=json.dumps(content)
assert dev['workspace_id'] not in encoded and dev['lakehouse_id'] not in encoded
definition={'parts':[{'path':'pipeline-content.json','payloadType':'InlineBase64','payload':base64.b64encode(encoded.encode()).decode()}]}
base='workspaces/'+s['workspace_id']+'/dataPipelines'
if not s.get('landing_pipeline_id'):
 matches=[x for x in request('GET','workspaces/'+s['workspace_id']+'/items').json()['value'] if x['displayName']=='pl_rebuild_official_landing'];assert len(matches)<=1
 item=matches[0] if matches else definition_operation(base,{'displayName':'pl_rebuild_official_landing','definition':definition})
 s['landing_pipeline_id']=item['id'];write_json(binding,s)
actual=definition_operation(base+'/'+s['landing_pipeline_id']+'/getDefinition')
found=json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path']=='pipeline-content.json')['payload']))
assert found['properties']==content['properties']
write_json(folder/'landing-definition.private.json',actual)
write_json(ROOT/'evidence/phase2/deployment/rebuild-landing-prepared.json',{'status':'rebuild_official_copy_prepared','sources':len(sources),'dev_destination_ids_absent':True,'job_started':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('Copy oficial dos cinco arquivos preparado no destino; execução ainda não iniciada',flush=True)
