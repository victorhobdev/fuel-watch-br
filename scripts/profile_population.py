"""Validar populacao municipal anual oficial, preservando snapshot e ausencias."""
import json,sys,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_sources import download
from fuelwatch.source import source_record,read_ibge
import pandas as pd

folder=ROOT/'evidence/phase2/context';folder.mkdir(parents=True,exist_ok=True)
out=ROOT/'data/artifacts/context';out.mkdir(parents=True,exist_ok=True)
base='https://servicodados.ibge.gov.br/api/v3/agregados/6579'
specs={'ibge_pop_metadata':{'url':base+'/metadados','filename':'metadata.json'}}
for year in [2024,2025,2026]:
    specs['ibge_pop_'+str(year)]={'url':base+'/periodos/'+str(year)+'/variaveis/9324?'+urllib.parse.urlencode({'localidades':'N6[all]'}),'filename':str(year)+'.json'}
records={};data={}
for key,spec in specs.items():
    try:record,payload=source_record(key)
    except (FileNotFoundError,StopIteration):
        download(key,spec);record,payload=source_record(key)
    records[key]={k:record.get(k) for k in ['url','sha256','bytes','last_modified','etag','finished_at_utc']}
    data[key]=read_ibge(payload,record.get('content_encoding'))
    print('Population source preserved',key,flush=True)
metadata=data['ibge_pop_metadata']
variable=next(x for x in metadata['variaveis'] if str(x['id'])=='9324')
assert variable['unidade'].lower()=='pessoas',variable
rows=[]
for year in [2024,2025,2026]:
    payload=data['ibge_pop_'+str(year)]
    assert len(payload)==1 and payload[0]['id']=='9324' and payload[0]['unidade'].lower()=='pessoas'
    for result in payload[0]['resultados']:
        for item in result['series']:
            local=item['localidade'];assert local['nivel']['id']=='N6'
            code=local['id'];assert len(code)==7 and code.isdigit()
            assert set(item['serie'])=={str(year)}
            value=item['serie'][str(year)]
            population=int(value) if value.isdigit() else None
            assert population is None or population>0
            rows.append({'municipio_ibge':code,'ano_referencia':year,'data_referencia':f'{year}-07-01','populacao':population,'valor_origem':value,'source_sha256':records['ibge_pop_'+str(year)]['sha256']})
f=pd.DataFrame(rows);assert not f.duplicated(['municipio_ibge','ano_referencia']).any()
f['populacao']=f['populacao'].astype('Int64')
f.to_parquet(out/'population.parquet',index=False)
report={'status':'official_population_profiled_locally','fabric_executed':False,'aggregate':'6579','variable':variable,'sources':records,'rows':len(f),'by_year':f.groupby('ano_referencia').agg(municipios=('municipio_ibge','size'),ausentes=('populacao',lambda s:int(s.isna().sum()))).reset_index().to_dict(orient='records'),'temporal_policy':'Contexto retrospectivo do mesmo ano; referencia em 1 de julho, nao disponibilidade na data da coleta. Snapshot atual sujeito a revisoes.','checked_at_utc':datetime.now(timezone.utc).isoformat()}
(folder/'population-profile.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'rows':report['rows'],'by_year':report['by_year']},ensure_ascii=True),flush=True)
