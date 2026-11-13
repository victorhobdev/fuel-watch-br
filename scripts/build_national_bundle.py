"""Bundle nacional imutavel, com hashes e notebook parametrizado."""
import json,hashlib,zipfile,shutil
from pathlib import Path
root=Path.cwd();out=root/'data/artifacts/national';bundle=out/'bundle';bundle.mkdir(exist_ok=True)
for name in ['reference.parquet','municipalities.parquet','thresholds.parquet','calendar.parquet','history.parquet','weekly.parquet']:
 shutil.copyfile(out/name,bundle/name)
for name in ['municipios.json','estados.json','municipios.http','estados.http']:
 shutil.copyfile(root/'.local/national'/name,bundle/name)
with zipfile.ZipFile(bundle/'fuelwatch_national_rules.zip','w',zipfile.ZIP_DEFLATED) as archive:
 for p in sorted((root/'fuelwatch').glob('*.py')):archive.write(p,'fuelwatch/'+p.name)
m=json.loads((out/'manifest.json').read_text(encoding='utf8'));m['files']={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(bundle.iterdir()) if p.name!='manifest.json'};raw=json.dumps(m,ensure_ascii=False,indent=2).encode('utf8');(bundle/'manifest.json').write_bytes(raw);sha=hashlib.sha256(raw).hexdigest();relative='national_input/'+sha
parameters=f'p_bundle_relative_path = {json.dumps(relative)}\np_manifest_sha256 = {json.dumps(sha)}\n'
source=(root/'notebooks/national_sources/10_brasil_todos_combustiveis.py').read_text(encoding='utf8');compile(source,'national','exec');nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'synapse_pyspark','display_name':'Synapse PySpark','language':'Python'},'language_info':{'name':'python'}},'cells':[{'cell_type':'code','metadata':{'tags':['parameters']} if i==0 else {},'execution_count':None,'outputs':[],'source':s.splitlines(keepends=True)} for i,s in enumerate([parameters,source])]};(root/'notebooks/10_brasil_todos_combustiveis.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8');(root/'.local/national/bundle-binding.json').write_text(json.dumps({'relative_path':relative,'manifest_sha256':sha},indent=2));print('National bundle ready',sha)
