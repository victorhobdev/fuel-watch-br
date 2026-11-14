"""Join anual retrospectivo e referencia de cobertura municipal sem ponderar preco."""
import json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1]
prices=pd.read_parquet(root/'data/artifacts/history/publication/reference.parquet')
prices['ano_referencia']=pd.to_datetime(prices['data_coleta']).dt.year
population=pd.read_parquet(root/'data/artifacts/context/population.parquet')
joined=prices.merge(population,on=['municipio_ibge','ano_referencia'],how='left',validate='many_to_one',sort=False)
assert len(joined)==len(prices)
assert prices.reset_index(drop=True).equals(joined[prices.columns].reset_index(drop=True)),'Join alterou campos da coleta'
before=sum(int(p*1000) for p in prices['preco_venda'])
after=sum(int(p*1000) for p in joined['preco_venda']);assert before==after
keys=['municipio_ibge','uf','ano_referencia','produto','moeda','unidade']
municipal=joined.groupby(keys,dropna=False).agg(coletas=('cnpj','size'),postos_observados=('cnpj','nunique'),preco_mediano=('preco_venda','median'),populacao=('populacao','first')).reset_index()
assert not municipal.duplicated(keys).any()
municipal['populacao']=municipal['populacao'].astype('Int64')
municipal['porte_populacional']=pd.cut(municipal['populacao'].astype(float),bins=[0,50000,100000,500000,float('inf')],labels=['ate_50mil','50mil_a_100mil','100mil_a_500mil','acima_500mil']).astype('string').fillna('sem_referencia')
municipal['postos_pesquisados_por_100mil']=municipal['postos_observados']/municipal['populacao']*100000
municipal.to_parquet(root/'data/artifacts/context/municipal_population.parquet',index=False)
summary={'status':'population_join_reference_validated_locally','fabric_executed':False,'before_rows':len(prices),'after_rows':len(joined),'before_sum_price_mills':before,'after_sum_price_mills':after,'original_business_fields_unchanged':True,'municipality_years':len(joined[['municipio_ibge','ano_referencia']].drop_duplicates()),'by_year':joined.groupby('ano_referencia').agg(coletas=('cnpj','size'),coletas_sem_populacao=('populacao',lambda s:int(s.isna().sum()))).reset_index().to_dict(orient='records'),'interpretation':'Postos pesquisados por 100 mil mede cobertura da pesquisa, nao densidade de todos os postos. Preco nao e dividido nem ponderado por populacao.','checked_at_utc':datetime.now(timezone.utc).isoformat()}
(root/'evidence/phase2/context/population-join-local.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:summary[k] for k in ['before_rows','after_rows','municipality_years','by_year']}),flush=True)
