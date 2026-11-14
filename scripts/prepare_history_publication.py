"""Referencia independente da publicacao conjunta 2024-2026H1; sem Fabric."""
import argparse,hashlib,json,sys
from datetime import date,timedelta,datetime,timezone
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from fuelwatch.m02_reference import TYPED_FIELDS,BUSINESS_FIELDS
from fuelwatch.national import IQR_KEYS

p=argparse.ArgumentParser();p.add_argument('--lab-source-summary',type=Path);args=p.parse_args()
if args.lab_source_summary:
    lab_path=args.lab_source_summary.resolve();assert lab_path.is_relative_to(ROOT/'data/artifacts/history/lab')
    input_summary=json.loads(lab_path.read_text(encoding='utf8'));assert input_summary.get('is_synthetic') is True
else:input_summary=json.loads((ROOT/'evidence/phase2/history/reference-summary.json').read_text(encoding='utf8'))
folder=ROOT/('data/artifacts/history/lab/publication' if args.lab_source_summary else 'data/artifacts/history/publication');folder.mkdir(exist_ok=True)
sources=input_summary['sources']
frames=[];versions=[]
for source in sources:
    if args.lab_source_summary and source.get('reference_path'):
        path=(ROOT/source['reference_path']).resolve();assert path.is_relative_to(ROOT/'data/artifacts/history/lab')
    else:path=ROOT/'data/artifacts/history'/source['source_id']/source['source_sha256']/'reference.parquet'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==source['parquet_sha256']
    frames.append(pd.read_parquet(path,columns=TYPED_FIELDS))
    versions.append({k:source[k] for k in ['source_id','source_sha256','csv_sha256','scope','counts']})
current=json.loads((ROOT/'data/artifacts/national/manifest.json').read_text(encoding='utf8'))
frames.append(pd.read_parquet(ROOT/'data/artifacts/national/reference.parquet',columns=TYPED_FIELDS))
versions.append({'source_id':'anp_2026_1','source_sha256':current['anp']['sha256'],'csv_sha256':current['anp']['csv_sha256'],'scope':current['scope'],'counts':current['counts']})
f=pd.concat(frames,ignore_index=True);del frames
assert len(f)==sum(x['counts']['accepted'] for x in versions)
assert not f.duplicated(['cnpj','produto','data_coleta','unidade']).any()
f['inicio_semana_iso']=f['data_coleta'].map(lambda d:d-timedelta(days=d.weekday()))
f['price_mills']=f['preco_venda'].map(lambda x:int(x*1000))
groups=f.groupby(IQR_KEYS,dropna=False)
bounds=groups.agg(coletas=('cnpj','size'),postos=('cnpj','nunique')).reset_index()
quantiles=groups['price_mills'].quantile([.25,.75]).unstack().reset_index().rename(columns={.25:'q25_mills',.75:'q75_mills'})
bounds=bounds.merge(quantiles,on=IQR_KEYS,validate='one_to_one')
bounds['iqr_lower_mills']=bounds['q25_mills']-1.5*(bounds['q75_mills']-bounds['q25_mills'])
bounds['iqr_upper_mills']=bounds['q75_mills']+1.5*(bounds['q75_mills']-bounds['q25_mills'])
bounds['iqr_avaliado']=(bounds['coletas']>=20)&(bounds['postos']>=5)
f=f.merge(bounds[IQR_KEYS+['iqr_lower_mills','iqr_upper_mills','iqr_avaliado']],on=IQR_KEYS,validate='many_to_one')
f['preco_incomum_iqr']=f['iqr_avaliado']&~f['price_mills'].between(f['iqr_lower_mills'],f['iqr_upper_mills'])
f[BUSINESS_FIELDS].to_parquet(folder/'reference.parquet',index=False)
bounds.to_parquet(folder/'thresholds.parquet',index=False)
attrs=['revenda_observada','bandeira_observada','municipio_ibge','uf']
days=f[['cnpj','data_coleta',*attrs]].drop_duplicates().sort_values(['cnpj','data_coleta'])
assert not days.duplicated(['cnpj','data_coleta']).any(),'Atributos diarios ambiguos exigem politica explicita'
previous=days.groupby('cnpj')[attrs].shift()
changed=(days[attrs]!=previous).any(axis=1)
history=days[changed].copy().rename(columns={'data_coleta':'observado_desde'})
history['observado_ate']=history.groupby('cnpj')['observado_desde'].shift(-1).where(lambda x:x.notna(),None)
history['posto_sk']=history['cnpj']+':'+history['observado_desde'].astype(str)
history[['posto_sk','cnpj',*attrs,'observado_desde','observado_ate']].to_parquet(folder/'history.parquet',index=False)
start=min(date.fromisoformat(v['scope']['date_start']) for v in versions);end=max(date.fromisoformat(v['scope']['date_end']) for v in versions)
calendar=pd.DataFrame({'data':[start+timedelta(days=i) for i in range((end-start).days+1)]})
calendar['data_sk']=calendar['data'].map(lambda x:int(x.strftime('%Y%m%d')))
calendar['inicio_semana_iso']=calendar['data'].map(lambda x:x-timedelta(days=x.weekday()))
calendar['ano_iso']=calendar['data'].map(lambda x:x.isocalendar().year);calendar['semana_iso']=calendar['data'].map(lambda x:x.isocalendar().week)
calendar.to_parquet(folder/'calendar.parquet',index=False)
weekly=f.groupby(['inicio_semana_iso','municipio_ibge','produto','moeda','unidade'],dropna=False).agg(coletas=('cnpj','size'),postos_observados=('cnpj','nunique'),soma_mills=('price_mills','sum'),min_mills=('price_mills','min'),max_mills=('price_mills','max'),precos_incomuns=('preco_incomum_iqr','sum')).reset_index()
weekly['ano_iso']=weekly['inicio_semana_iso'].map(lambda x:x.isocalendar().year);weekly['semana_iso']=weekly['inicio_semana_iso'].map(lambda x:x.isocalendar().week)
for old,new in [('soma_mills','soma_precos'),('min_mills','preco_minimo'),('max_mills','preco_maximo')]:weekly[new]=weekly[old].map(lambda n:Decimal(int(n))/1000)
weekly=weekly[['inicio_semana_iso','ano_iso','semana_iso','municipio_ibge','produto','moeda','unidade','coletas','postos_observados','soma_precos','preco_minimo','preco_maximo','precos_incomuns']]
weekly.to_parquet(folder/'weekly.parquet',index=False)
summary={'status':'joint_historical_publication_reference_prepared','fabric_executed':False,'is_synthetic':bool(args.lab_source_summary),'sources':versions,'date_start':start.isoformat(),'date_end':end.isoformat(),'calendar_days':len(calendar),'rows':len(f),'stations':int(f['cnpj'].nunique()),'municipalities':int(f['municipio_ibge'].nunique()),'ufs':int(f['uf'].nunique()),'products':int(f['produto'].nunique()),'station_versions':len(history),'weekly_groups':len(weekly),'unusual':int(f['preco_incomum_iqr'].sum()),'iqr_not_evaluated_rows':int((~f['iqr_avaliado']).sum()),'ibge_sha256':current['ibge']['sha256'],'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(folder.glob('*.parquet'))},'prepared_at_utc':datetime.now(timezone.utc).isoformat()}
evidence=ROOT/('evidence/phase2/history/lab' if args.lab_source_summary else 'evidence/phase2/history');evidence.mkdir(exist_ok=True)
if args.lab_source_summary:summary['lab_source_ids']=[s['source_id'] for s in sources if s.get('reference_path')]
(evidence/'publication-reference.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:summary[k] for k in ['rows','calendar_days','stations','municipalities','ufs','products','station_versions','weekly_groups','unusual','iqr_not_evaluated_rows']}),flush=True)
