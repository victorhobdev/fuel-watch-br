"""Ensaio alternado de consulta: view versus cópia materializada de laboratório."""
import hashlib
import json
import statistics
import time
from datetime import datetime,timezone
from client import ROOT
from warehouse import connect,results
from evidence import write_json

def fingerprint(rows):
    lines=sorted(json.dumps(row,sort_keys=True,default=str,separators=(',',':')) for row in rows)
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()

with connect() as cn:
 cn.timeout=900
 cur=cn.cursor()
 before=results(cur.execute('SELECT * FROM gold_hist.publication'))[0]
 source='analise_hist.populacao_municipio'
 target='lab_f2.population_cache'
 results(cur.execute("IF SCHEMA_ID('lab_f2') IS NULL EXEC('CREATE SCHEMA lab_f2');"))
 exists=cur.execute("SELECT COUNT(*) FROM sys.tables WHERE schema_id=SCHEMA_ID('lab_f2') AND name='population_cache'").fetchone()[0]
 if not exists:results(cur.execute('CREATE TABLE '+target+' AS SELECT * FROM '+source))
 baseline=results(cur.execute('SELECT * FROM '+source))[0]
 cached=results(cur.execute('SELECT * FROM '+target))[0]
 assert len(baseline)==len(cached) and fingerprint(baseline)==fingerprint(cached),'Cópia não corresponde à publicação; investigar antes de medir'
 measurements=[]
 for warmup,order in [(True,['view','cache']),(False,['view','cache']),(False,['cache','view']),(False,['view','cache'])]:
  for condition in order:
   start=time.monotonic()
   actual=results(cur.execute('SELECT * FROM '+(source if condition=='view' else target)))[0]
   seconds=time.monotonic()-start
   assert len(actual)==len(baseline) and fingerprint(actual)==fingerprint(baseline)
   measurements.append({'condition':condition,'warmup':warmup,'seconds':seconds,'rows':len(actual)})
   print(condition,'warmup' if warmup else 'measured',round(seconds,3),flush=True)
 assert before==results(cur.execute('SELECT * FROM gold_hist.publication'))[0]
 summary={}
 for condition in ['view','cache']:
  values=[x['seconds'] for x in measurements if x['condition']==condition and not x['warmup']]
  summary[condition]={'median_seconds':statistics.median(values),'minimum_seconds':min(values),'maximum_seconds':max(values),'samples':len(values)}
 write_json(ROOT/'evidence/phase2/performance/context-query.json',{
  'status':'context_query_materialization_experiment_reconciled','environment':'fabric','checked_at_utc':datetime.now(timezone.utc).isoformat(),
  'hypothesis':'Materialização evita recomputar janelas e joins da view em consultas repetidas.',
  'source':source,'laboratory_copy':target,'rows':len(baseline),'content_sha256':fingerprint(baseline),
  'measurements':measurements,'summary':summary,'official_publication_unchanged':True,
  'limitations':'Mede consulta completa via TDS incluindo transferência. Não mede DAX ou pipeline fim a fim; cache do serviço não controlado; CU não medido. Cópia não promovida para produção.'})
 print(json.dumps(summary),flush=True)
