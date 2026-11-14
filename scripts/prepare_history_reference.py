"""Referencia local independente por versao; nao e execucao Spark/Fabric."""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pandas as pd
from fuelwatch.contract import validate_row
from fuelwatch.national import PRODUCT_UNITS, national_reference
from fuelwatch.source import source_record, read_anp

out = ROOT/'data/artifacts/history'
out.mkdir(parents=True,exist_ok=True)
evidence = ROOT/'evidence/phase2/history'
_, lookup = national_reference(json.loads((ROOT/'.local/national/municipios.json').read_bytes()),json.loads((ROOT/'.local/national/estados.json').read_bytes()))
summary=[]
for year,semester in [(2024,1),(2024,2),(2025,1),(2025,2)]:
    source_id=f'anp_{year}_{semester}'
    record,payload=source_record(source_id)
    profile=json.loads((evidence/(source_id+'-profile.json')).read_text(encoding='utf8'))
    assert record['sha256']==profile['source_sha256']
    folder=out/source_id/record['sha256'];folder.mkdir(parents=True,exist_ok=True)
    frame,meta=read_anp(payload)
    scope={'scope_id':source_id+'-br-todos','date_start':profile['declared_period']['start'],'date_end':profile['declared_period']['end'],'product_units':PRODUCT_UNITS,'contract_version':'history-1.0'}
    if (year,semester)==(2025,2):
        scope['unit_aliases']={'R$ / m3':'R$ / m³'}
    accepted=[];seen=set();invalid=0;duplicates=0;reasons_count=Counter();headers=frame.columns.tolist()
    with (folder/'invalid.jsonl').open('w',encoding='utf8') as quarantine, (folder/'duplicates.jsonl').open('w',encoding='utf8') as duplicate_audit:
        for number,values in enumerate(frame.itertuples(index=False,name=None),start=2):
            raw=dict(zip(headers,values));typed,reasons=validate_row(raw,lookup,scope)
            if reasons:
                invalid+=1;reasons_count.update(reasons)
                quarantine.write(json.dumps({'source_record':number,'source_sha256':record['sha256'],'reasons':reasons,'raw':raw},ensure_ascii=False)+'\n')
                continue
            if values in seen:
                duplicates+=1
                duplicate_audit.write(json.dumps({'source_record':number,'source_sha256':record['sha256'],'raw':raw},ensure_ascii=False)+'\n')
                continue
            seen.add(values)
            typed.update({'source_record':number,'source_id':source_id,'source_sha256':record['sha256'],'raw_json':json.dumps(raw,ensure_ascii=False)})
            accepted.append(typed)
    del seen,frame,payload
    f=pd.DataFrame(accepted);del accepted
    key=['cnpj','produto','data_coleta','unidade']
    conflict=f.duplicated(key,keep=False)
    f.loc[conflict].to_parquet(folder/'conflicts.parquet',index=False)
    conflicts=int(conflict.sum());f=f.loc[~conflict].copy()
    attrs=['revenda_observada','bandeira_observada','municipio_ibge','uf']
    days=f[['cnpj','data_coleta',*attrs]].drop_duplicates()
    ambiguous=days.duplicated(['cnpj','data_coleta'],keep=False)
    days.loc[ambiguous].to_parquet(folder/'ambiguous_station_days.parquet',index=False)
    target=folder/'reference.parquet';f.to_parquet(target,index=False)
    counts={'received':profile['rows'],'invalid':invalid,'exact_duplicate_excess':duplicates,'conflicting_rows':conflicts,'accepted':len(f)}
    assert counts['received']==sum(v for k,v in counts.items() if k!='received')
    assert not f.duplicated(key).any()
    metrics=f.assign(price_mills=f['preco_venda'].map(lambda x:int(x*1000))).groupby(['uf','produto','moeda','unidade']).agg(coletas=('cnpj','size'),postos=('cnpj','nunique'),municipios=('municipio_ibge','nunique'),soma_mills=('price_mills','sum')).reset_index().to_dict(orient='records')
    item={'source_id':source_id,'scope':scope,'source_sha256':record['sha256'],'csv_sha256':meta['csv_sha256'],'counts':counts,'invalid_reasons':dict(reasons_count),'ambiguous_station_day_records':int(ambiguous.sum()),'parquet_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'ufs':int(f['uf'].nunique()),'municipalities':int(f['municipio_ibge'].nunique()),'stations':int(f['cnpj'].nunique()),'by_uf_product_unit':metrics,'fabric_executed':False,'prepared_at_utc':datetime.now(timezone.utc).isoformat()}
    summary.append(item)
    (evidence/(source_id+'-reference.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'source_id':source_id,'counts':counts,'invalid_reasons':dict(reasons_count),'ambiguous_station_day_records':int(ambiguous.sum())},ensure_ascii=True),flush=True)
    del f,days
(evidence/'reference-summary.json').write_text(json.dumps({'status':'local_historical_reference_prepared','fabric_executed':False,'sources':summary},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
