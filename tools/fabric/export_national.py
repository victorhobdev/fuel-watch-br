"""Exporta coletas nacionais reais do Warehouse para CSV gzip, preservando texto."""
import csv,gzip,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from client import ROOT
from warehouse import connect,results

c=json.loads((ROOT/'.local/fabric-environment.json').read_text());m=json.loads((ROOT/'data/artifacts/national/manifest.json').read_text(encoding='utf8'));out=ROOT/'data/processed';out.mkdir(exist_ok=True);target=out/'anp_brasil_2026_1.csv.gz';partial=out/'anp_brasil_2026_1.csv.gz.partial';counts=Counter();mills=Counter();n=0
with connect(c) as conn:
 cur=conn.cursor().execute('SELECT * FROM gold_br.coletas');columns=[x[0] for x in cur.description]
 with gzip.open(partial,'wt',encoding='utf-8-sig',newline='') as stream:
  writer=csv.writer(stream,delimiter=';');writer.writerow(columns)
  while True:
   batch=cur.fetchmany(10000)
   if not batch:break
   for row in batch:
    d=dict(zip(columns,row));key=(d['uf'],d['produto'],d['unidade']);counts[key]+=1;mills[key]+=int(d['preco_venda']*1000);n+=1;writer.writerow([str(v).replace('.',',') if name=='preco_venda' else v for name,v in zip(columns,row)])
 assert n==m['counts']['accepted']
 for r in m['by_uf_product_unit']:
  key=(r['uf'],r['produto'],r['unidade']);assert counts[key]==r['coletas'] and mills[key]==r['soma_mills']
 quality=results(conn.cursor().execute('SELECT classificacao_preco,COUNT_BIG(*) AS coletas FROM gold_br.coletas GROUP BY classificacao_preco'))[0]
 assert next(x['coletas'] for x in quality if x['classificacao_preco']=='nao_avaliado')==m['iqr_not_evaluated_rows']
 assert next(x['coletas'] for x in quality if x['classificacao_preco']=='incomum_valido')==m['unusual']
partial.replace(target);report={'status':'warehouse_export_verified','source':'wh_fuelwatch.gold_br.coletas','rows':n,'columns':columns,'file':str(target.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size,'counts_and_sums_by_uf_product_unit_equal':True,'quality_counts':quality,'checked_at_utc':datetime.now(timezone.utc).isoformat()};(ROOT/'evidence/fabric/national/export-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
