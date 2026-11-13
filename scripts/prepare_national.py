"""Perfil e referencia independente nacional: nao executa Fabric."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone,timedelta,date
from decimal import Decimal
import pandas as pd
from fuelwatch.contract import validate_row
from fuelwatch.national import SCOPE,national_reference,IQR_KEYS
from fuelwatch.source import source_record,read_anp
from fuelwatch.m02_reference import BUSINESS_FIELDS

out=Path('data/artifacts/national');out.mkdir(parents=True,exist_ok=True)
refs=Path('.local/national');municipalities=json.loads((refs/'municipios.json').read_bytes());states=json.loads((refs/'estados.json').read_bytes());ref,lookup=national_reference(municipalities,states)
source,payload=source_record('anp_2026_1');frame,meta=read_anp(payload)
accepted=[];invalid=[];duplicates=[];seen=set();headers=frame.columns.tolist()
for number,values in enumerate(frame.itertuples(index=False,name=None),start=2):
 raw=dict(zip(headers,values));record,reasons=validate_row(raw,lookup,SCOPE)
 if reasons:invalid.append({'source_record':number,'raw':raw,'reasons':reasons});continue
 if values in seen:duplicates.append({'source_record':number,'raw':raw});continue
 seen.add(values);accepted.append(record)
del seen
f=pd.DataFrame(accepted);keys=['cnpj','produto','data_coleta','unidade'];conflict=f.duplicated(keys,keep=False);conflicts=f[conflict].copy();f=f[~conflict].copy()
attrs=['revenda_observada','bandeira_observada','municipio_ibge','uf'];daily=f[['cnpj','data_coleta',*attrs]].drop_duplicates();assert not daily.duplicated(['cnpj','data_coleta']).any(),'Atributos conflitantes no mesmo dia exigem politica explicita'
f['inicio_semana_iso']=f['data_coleta'].map(lambda d:d-timedelta(days=d.weekday()));f['price_mills']=f['preco_venda'].map(lambda p:int(p*1000))
groups=f.groupby(IQR_KEYS,dropna=False);threshold=groups.agg(coletas=('cnpj','size'),postos=('cnpj','nunique')).reset_index();q=groups['price_mills'].quantile([.25,.75]).unstack().reset_index().rename(columns={.25:'q25_mills',.75:'q75_mills'});threshold=threshold.merge(q,on=IQR_KEYS,validate='one_to_one');threshold['iqr_lower_mills']=threshold['q25_mills']-1.5*(threshold['q75_mills']-threshold['q25_mills']);threshold['iqr_upper_mills']=threshold['q75_mills']+1.5*(threshold['q75_mills']-threshold['q25_mills']);threshold['iqr_avaliado']=(threshold['coletas']>=20)&(threshold['postos']>=5)
f=f.merge(threshold[IQR_KEYS+['iqr_lower_mills','iqr_upper_mills','iqr_avaliado']],on=IQR_KEYS,validate='many_to_one');f['preco_incomum_iqr']=f['iqr_avaliado']&((f['price_mills']<f['iqr_lower_mills'])|(f['price_mills']>f['iqr_upper_mills']))
refdf=pd.DataFrame(ref);refdf.to_parquet(out/'municipalities.parquet',index=False);threshold.to_parquet(out/'thresholds.parquet',index=False);f[BUSINESS_FIELDS].to_parquet(out/'reference.parquet',index=False)
calendar=pd.DataFrame({'data':[date(2026,1,1)+timedelta(days=i) for i in range(181)]});calendar['data_sk']=calendar['data'].map(lambda d:int(d.strftime('%Y%m%d')));calendar['inicio_semana_iso']=calendar['data'].map(lambda d:d-timedelta(days=d.weekday()));calendar['ano_iso']=calendar['data'].map(lambda d:d.isocalendar().year);calendar['semana_iso']=calendar['data'].map(lambda d:d.isocalendar().week);calendar.to_parquet(out/'calendar.parquet',index=False)
daily=daily.sort_values(['cnpj','data_coleta']);prior=daily.groupby('cnpj')[attrs].shift();change=(daily[attrs]!=prior).any(axis=1);history=daily[change].copy().rename(columns={'data_coleta':'observado_desde'});history['observado_ate']=history.groupby('cnpj')['observado_desde'].shift(-1).where(lambda s:s.notna(),None);history['posto_sk']=history['cnpj']+':'+history['observado_desde'].astype(str);history[['posto_sk','cnpj',*attrs,'observado_desde','observado_ate']].to_parquet(out/'history.parquet',index=False)
weekly=f.groupby(['inicio_semana_iso','municipio_ibge','produto','moeda','unidade'],dropna=False).agg(coletas=('cnpj','size'),postos_observados=('cnpj','nunique'),soma_mills=('price_mills','sum'),min_mills=('price_mills','min'),max_mills=('price_mills','max'),precos_incomuns=('preco_incomum_iqr','sum')).reset_index();weekly['ano_iso']=weekly['inicio_semana_iso'].map(lambda d:d.isocalendar().year);weekly['semana_iso']=weekly['inicio_semana_iso'].map(lambda d:d.isocalendar().week)
for old,new in [('soma_mills','soma_precos'),('min_mills','preco_minimo'),('max_mills','preco_maximo')]:weekly[new]=weekly[old].map(lambda n:Decimal(int(n))/1000)
weekly=weekly[['inicio_semana_iso','ano_iso','semana_iso','municipio_ibge','produto','moeda','unidade','coletas','postos_observados','soma_precos','preco_minimo','preco_maximo','precos_incomuns']];weekly.to_parquet(out/'weekly.parquet',index=False)
counts={'received':len(frame),'invalid':len(invalid),'exact_duplicate_excess':len(duplicates),'conflicting_rows':len(conflicts),'accepted':len(f)};assert counts['received']==sum(v for k,v in counts.items() if k!='received');assert counts['accepted']==422412
quality={'invalid':invalid,'duplicates':duplicates,'conflicts':conflicts.to_dict(orient='records')};(out/'local-quality.json').write_text(json.dumps(quality,default=str,ensure_ascii=False,indent=2),encoding='utf8')
metrics=f.groupby(['uf','produto','moeda','unidade']).agg(coletas=('cnpj','size'),postos=('cnpj','nunique'),municipios=('municipio_ibge','nunique'),soma_mills=('price_mills','sum'),incomuns=('preco_incomum_iqr','sum')).reset_index().to_dict(orient='records')
m={'status':'national_local_reference_prepared','fabric_executed':False,'scope':SCOPE,'anp':{'sha256':source['sha256'],'rows':len(frame),**meta},'ibge':{'sha256':hashlib.sha256((refs/'municipios.json').read_bytes()).hexdigest(),'http_snapshot':json.loads((refs/'municipios-source.json').read_text()),'states_sha256':hashlib.sha256((refs/'estados.json').read_bytes()).hexdigest()},'counts':counts,'stations':f['cnpj'].nunique(),'municipalities':f['municipio_ibge'].nunique(),'ufs':f['uf'].nunique(),'products':f['produto'].nunique(),'reference_municipalities':len(ref),'station_versions':len(history),'weekly_groups':len(weekly),'unusual':int(f['preco_incomum_iqr'].sum()),'iqr_not_evaluated_rows':int((~f['iqr_avaliado']).sum()),'iqr_method':'exact linear quartiles in integer mills, by UF/product/unit/currency/ISO week; >=20 observations and >=5 stations','municipality_alias':{'source':'RS/SANTANA DO LIVRAMENTO','ibge':'4317103','matched_rows':int((f['municipio_ibge']=='4317103').sum())},'by_uf_product_unit':metrics,'prepared_at_utc':datetime.now(timezone.utc).isoformat()};(out/'manifest.json').write_text(json.dumps(m,default=int,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:m[k] for k in ['counts','stations','municipalities','ufs','products','station_versions','weekly_groups','unusual','iqr_not_evaluated_rows']},default=int),flush=True)
