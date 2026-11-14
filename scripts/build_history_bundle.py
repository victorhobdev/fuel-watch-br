"""Empacota referencias locais e contrato compartilhado para verificacao no Spark."""
import hashlib,json,shutil,zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
folder=root/'data/artifacts/history/bundle';folder.mkdir(parents=True,exist_ok=True)
summary=json.loads((root/'evidence/phase2/history/reference-summary.json').read_text(encoding='utf8'))
profiles={p['source_id']:p for p in json.loads((root/'evidence/phase2/history/profile-summary.json').read_text(encoding='utf8'))['profiles']}
sources=[]
for source in summary['sources']:
    item={k:source[k] for k in ['source_id','scope','source_sha256','csv_sha256','counts']}
    item['filename']=profiles[item['source_id']]['source_url'].rsplit('/',1)[-1]
    sources.append(item)
    shutil.copyfile(root/'data/artifacts/history'/item['source_id']/item['source_sha256']/'reference.parquet',folder/(item['source_id']+'.parquet'))
for name in ['municipios.json','estados.json']:
    shutil.copyfile(root/'.local/national'/name,folder/name)
with zipfile.ZipFile(folder/'rules.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root/'fuelwatch').glob('*.py')):archive.write(path,'fuelwatch/'+path.name)
manifest={'sources':sources,'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.name!='manifest.json'}}
raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8');(folder/'manifest.json').write_bytes(raw)
sha=hashlib.sha256(raw).hexdigest();private=root/'.local/phase2-history'
private.mkdir(exist_ok=True)
(private/'bundle.json').write_text(json.dumps({'relative_path':'history_input/'+sha,'manifest_sha256':sha},indent=2))
source=(root/'notebooks/national_sources/11_historico_bronze_silver.py').read_text(encoding='utf8');compile(source,'history','exec')
parameters=f'p_bundle_relative_path = {json.dumps("history_input/"+sha)}\np_manifest_sha256 = {json.dumps(sha)}\np_landing_run_id = ""\n'
nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'synapse_pyspark','display_name':'Synapse PySpark','language':'Python'},'language_info':{'name':'python'}},'cells':[{'cell_type':'code','metadata':{'tags':['parameters']} if i==0 else {},'execution_count':None,'outputs':[],'source':text.splitlines(keepends=True)} for i,text in enumerate([parameters,source])]}
(root/'notebooks/11_historico_bronze_silver.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
print('Historical bundle prepared:',sha,flush=True)
