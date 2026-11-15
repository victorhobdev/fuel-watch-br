"""Reconcilia comparações exploratórias estratificadas por UF e trimestre."""
import json
import argparse
from datetime import datetime,timezone
from client import ROOT
from warehouse import connect,results
from evidence import write_json

expected=json.loads((ROOT/'evidence/phase2/context/answers-local.json').read_text(encoding='utf8'))['answers']['weather_rain_and_temperature']
parser=argparse.ArgumentParser();parser.add_argument('--rebuild',action='store_true');args=parser.parse_args()
query='''WITH base AS (
 SELECT m.uf,YEAR(m.inicio_semana_iso) AS ano,DATEPART(quarter,m.inicio_semana_iso) AS trimestre,
 CASE WHEN w.observed_rain_mm<10 THEN 'abaixo_10mm' WHEN w.observed_rain_mm<40 THEN '10_a_40mm' ELSE '40mm_ou_mais' END AS chuva,
 m.municipio_ibge,m.mediana_municipio,w.mean_temperature_degC
 FROM analise_hist.municipio_semana m JOIN lh_fuelwatch.dbo.f2_context_weather_municipal_weekly w
 ON m.municipio_ibge=w.municipio_ibge AND m.inicio_semana_iso=w.week_start
 WHERE m.produto='GASOLINA' AND m.moeda='BRL' AND m.unidade='litro' AND m.benchmark_elegivel=1
 AND w.rain_eligible=1 AND w.temperature_eligible=1 AND w.partial_boundary_week=0
 AND m.uf IN ('RJ','SP') AND YEAR(m.inicio_semana_iso)=2025
), counts AS (
 SELECT uf,ano,trimestre,chuva,COUNT_BIG(*) AS municipios_semanas,COUNT(DISTINCT municipio_ibge) AS municipios
 FROM base GROUP BY uf,ano,trimestre,chuva
), quantiles AS (
 SELECT DISTINCT uf,ano,trimestre,chuva,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY mediana_municipio) OVER(PARTITION BY uf,ano,trimestre,chuva) AS mediana_precos,
 PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY mediana_municipio) OVER(PARTITION BY uf,ano,trimestre,chuva) AS q1_precos,
 PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY mediana_municipio) OVER(PARTITION BY uf,ano,trimestre,chuva) AS q3_precos,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY mean_temperature_degC) OVER(PARTITION BY uf,ano,trimestre,chuva) AS mediana_temperatura
 FROM base
)
SELECT c.*,q.mediana_precos,q.q1_precos,q.q3_precos,q.mediana_temperatura FROM counts c JOIN quantiles q
 ON c.uf=q.uf AND c.ano=q.ano AND c.trimestre=q.trimestre AND c.chuva=q.chuva
ORDER BY c.uf,c.ano,c.trimestre,c.chuva'''
with connect() as cn:
 cn.timeout=900
 actual=results(cn.cursor().execute(query))[0]
 assert len(actual)==len(expected)
 for a,b in zip(actual,expected):
  assert a.keys()==b.keys()
  for k in a:
   if k in {'uf','chuva'}:assert a[k]==b[k],(a,b)
   else:assert abs(float(a[k])-float(b[k]))<0.000001,(k,a,b)
 write_json(ROOT/('evidence/phase2/deployment/rebuild-weather-answers.json' if args.rebuild else 'evidence/phase2/context/weather-answers-fabric.json'),{
  'status':'weather_stratified_answers_reconciled','environment':'fabric','checked_at_utc':datetime.now(timezone.utc).isoformat(),
  'query':query,'answers':actual,'interpretation':'Associação descritiva; chuva observada nas horas válidas, sem imputação. Localização, sazonalidade e composição da amostra permanecem fatores de confusão.'})
 print('Recortes meteorológicos reconciliados:',len(actual),flush=True)
