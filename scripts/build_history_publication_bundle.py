"""Bundle imutavel do candidato historico conjunto."""
import hashlib,json,shutil,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'data/artifacts/history/publication-bundle';folder.mkdir(exist_ok=True)
m=json.loads((root/'evidence/phase2/history/publication-reference.json').read_text(encoding='utf8'))
for name,spec in m['files'].items():
    source=root/'data/artifacts/history/publication'/name;assert hashlib.sha256(source.read_bytes()).hexdigest()==spec['sha256']
    shutil.copyfile(source,folder/name)
shutil.copyfile(root/'data/artifacts/national/municipalities.parquet',folder/'municipalities.parquet')
with zipfile.ZipFile(folder/'rules.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((root/'fuelwatch').glob('*.py')):archive.write(path,'fuelwatch/'+path.name)
m['files']={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.name!='manifest.json'}
raw=json.dumps(m,ensure_ascii=False,indent=2).encode('utf8');(folder/'manifest.json').write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
(root/'.local/phase2-history/publication-bundle.json').write_text(json.dumps({'relative_path':'history_publication_input/'+sha,'manifest_sha256':sha},indent=2))
source=(root/'notebooks/national_sources/12_historico_publicacao.py').read_text(encoding='utf8');compile(source,'history-publication','exec')
parameters=f'p_bundle_relative_path = {json.dumps("history_publication_input/"+sha)}\np_manifest_sha256 = {json.dumps(sha)}\np_fault_stage = "none"\n'
nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'synapse_pyspark','display_name':'Synapse PySpark','language':'Python'},'language_info':{'name':'python'}},'cells':[{'cell_type':'code','metadata':{'tags':['parameters']} if i==0 else {},'execution_count':None,'outputs':[],'source':text.splitlines(keepends=True)} for i,text in enumerate([parameters,source])]}
(root/'notebooks/12_historico_publicacao.ipynb').write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
print('Joint historical publication bundle prepared:',sha,flush=True)
