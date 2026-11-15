"""Fixa uma referência histórica reconciliada para o laboratório sintético."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

root=Path(__file__).resolve().parents[1]
verification=json.loads((root/'evidence/phase2/analytics-history/warehouse-verification.json').read_text())
assert verification['status']=='analytics_full_comparison_passed'
reference=pd.read_parquet(root/'data/artifacts/analytics-history/referencia_uf_semana.parquet')
publication=json.loads((root/'evidence/phase2/history/publication-reference.json').read_text(encoding='utf8'))
full_week=pd.to_datetime(reference.inicio_semana_iso)+pd.Timedelta(days=6)<=pd.Timestamp(publication['date_end'])
eligible=reference.loc[(reference.uf=='RJ') & (reference.produto=='GASOLINA') &
                       (reference.moeda=='BRL') & (reference.unidade=='litro') &
                       (reference.postos_referencia>=10) & full_week].sort_values('inicio_semana_iso')
assert len(eligible)>0
row=eligible.iloc[-1]
benchmark={'contract_version':'synthetic-historical-benchmark-1',
 'source_publication':verification['source_publication'][0],
 'reference_business_sha256':verification['tables']['referencia_uf_semana']['business_sha256'],
 'uf':row.uf,'produto':row.produto,'moeda':row.moeda,'unidade':row.unidade,
 'week_start':str(row.inicio_semana_iso),'median':str(row.mediana_uf),
 'stations':int(row.postos_referencia),
 'available_for_lab_at_utc':datetime.now(timezone.utc).isoformat(),
 'maximum_reference_age_days':180,
 'missing_or_stale_policy':'unclassified_no_alert',
 'event_time_policy':'synthetic events at or after available_for_lab_at_utc; historical reference explicitly dated',
 'threshold_policy':'strictly greater than median times 1.10; synthetic scenario, not fraud detection',
 'is_synthetic_lab':True,'official_observations_modified':False}
identity=hashlib.sha256(json.dumps(benchmark,sort_keys=True,separators=(',',':')).encode()).hexdigest()
benchmark['benchmark_version']=identity
folder=root/'data/artifacts/alert-benchmark'/identity
folder.mkdir(parents=True,exist_ok=False)
(folder/'benchmark.json').write_text(json.dumps(benchmark,indent=2,default=str)+'\n',encoding='utf8')
evidence=root/'evidence/phase2/streaming'
evidence.mkdir(parents=True,exist_ok=True)
(evidence/'benchmark.json').write_text(json.dumps(benchmark,indent=2,default=str)+'\n',encoding='utf8')
print(json.dumps({'benchmark_version':identity,'week_start':benchmark['week_start'],'median':benchmark['median'],'stations':benchmark['stations'],'status':'prepared_not_emitted'}))
