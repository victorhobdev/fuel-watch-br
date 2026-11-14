"""Empacotar a correcao antiga isolada; mesmos motores Spark usados no oficial."""
import hashlib,json,shutil,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];base=root/'data/artifacts/history/lab';private=root/'.local/phase2-history'
summary=json.loads((base/'source-summary.json').read_text(encoding='utf8'));assert summary['is_synthetic']
corrected=next(s for s in summary['sources'] if s.get('reference_path'))
fixture=json.loads((root/'evidence/phase2/history/lab/fixture.json').read_text(encoding='utf8'))
spec={k:corrected[k] for k in ['source_id','source_sha256','csv_sha256','scope','counts']};spec['filename']='lab_ca_2024_01.zip'
bindings={}
for kind in ['versions','publication']:
    folder=base/(kind+'-bundle');folder.mkdir(exist_ok=True)
    if kind=='versions':
        shutil.copyfile(root/corrected['reference_path'],folder/(spec['source_id']+'.parquet'))
        for name in ['municipios.json','estados.json']:shutil.copyfile(root/'.local/national'/name,folder/name)
        manifest={'is_synthetic':True,'sources':[spec]}
        name='13_historico_correcao_lab';source_file='11_historico_bronze_silver.py'
    else:
        manifest=json.loads((root/'evidence/phase2/history/lab/publication-reference.json').read_text(encoding='utf8'));assert manifest['is_synthetic']
        for name,file in manifest['files'].items():
            path=base/'publication'/name;assert hashlib.sha256(path.read_bytes()).hexdigest()==file['sha256'];shutil.copyfile(path,folder/name)
        shutil.copyfile(root/'data/artifacts/national/municipalities.parquet',folder/'municipalities.parquet')
        name='14_historico_publicacao_lab';source_file='12_historico_publicacao.py'
    with zipfile.ZipFile(folder/'rules.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((root/'fuelwatch').glob('*.py')):archive.write(path,'fuelwatch/'+path.name)
    manifest['files']={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.iterdir()) if p.name!='manifest.json'}
    payload=json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf8');(folder/'manifest.json').write_bytes(payload);sha=hashlib.sha256(payload).hexdigest()
    relative='lab/history-correction/input/'+sha
    bindings[kind]={'relative_path':relative,'manifest_sha256':sha,'folder':folder.relative_to(root).as_posix(),'notebook_name':name}
    params=f'p_mode = "lab"\np_bundle_relative_path = {json.dumps(relative)}\np_manifest_sha256 = {json.dumps(sha)}\n'
    params+='p_landing_run_id = ""\n' if kind=='versions' else 'p_fault_stage = "none"\n'
    source=(root/'notebooks/national_sources'/source_file).read_text(encoding='utf8');compile(source,name,'exec')
    nb={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'name':'synapse_pyspark','display_name':'Synapse PySpark','language':'Python'},'language_info':{'name':'python'}},'cells':[{'cell_type':'code','metadata':{'tags':['parameters']} if i==0 else {},'execution_count':None,'outputs':[],'source':s.splitlines(keepends=True)} for i,s in enumerate([params,source])]}
    (root/'notebooks'/(name+'.ipynb')).write_text(json.dumps(nb,ensure_ascii=False,indent=2),encoding='utf8')
bindings['archive']={'source_sha256':fixture['corrected_source_sha256'],'local_path':(base/fixture['corrected_source_sha256']/'lab_ca_2024_01.zip').relative_to(root).as_posix(),'relative_path':'lab/history-correction/input-archives/'+fixture['corrected_source_sha256']+'/lab_ca_2024_01.zip'}
(private/'lab-bundles.json').write_text(json.dumps(bindings,indent=2)+'\n')
sql=root/'sql/history/lab';sql.mkdir(exist_ok=True)
for path in (root/'sql/history').glob('*.sql'):
    text=path.read_text(encoding='utf8').replace('gold_hist','lab_gold_hist').replace('hist_transfer_','lab_hist_transfer_').replace('hist_expected_','lab_hist_expected_').replace('is_synthetic=0','is_synthetic=1').replace('CAST(0 AS bit)','CAST(1 AS bit)').replace("'anp-historico-br-todos'","'lab-anp-historico-br-todos'")
    (sql/path.name).write_text(text,encoding='utf8')
print('Isolated lab notebooks/bundles/SQL prepared; no Fabric job started',flush=True)
