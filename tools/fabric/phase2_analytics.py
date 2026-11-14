"""Implanta views analiticas sem alterar a Gold e verifica conteudo completo por hash tipado."""
import argparse,json,re,hashlib,time,sys
from datetime import datetime,timezone
from client import ROOT
from warehouse import connect,results
sys.path.insert(0,str(ROOT))
from fuelwatch.analytics import row_hash

parser=argparse.ArgumentParser();parser.add_argument('--deploy',action='store_true');parser.add_argument('--verify',action='store_true');args=parser.parse_args();assert args.deploy or args.verify
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());out=ROOT/'evidence/phase2/analytics';out.mkdir(parents=True,exist_ok=True);record={'environment':'fabric','started_at_utc':datetime.now(timezone.utc).isoformat(),'tables':{}}
with connect(c) as cn:
 cn.timeout=600;cur=cn.cursor();before=results(cur.execute('SELECT * FROM gold_br.publication'))[0]
 if args.deploy:
  for i,sql in enumerate(re.split(r'(?m)^GO\s*$',(ROOT/'sql/analytics/01_national_benchmarks.sql').read_text(encoding='utf8'))):
   if sql.strip():results(cur.execute(sql));print('Analytical definition accepted',i,flush=True)
 if args.verify:
  expected=json.loads((ROOT/'data/artifacts/analytics/reference.json').read_text())
  for name,spec in expected.items():
   started=time.monotonic();cur.execute('SELECT '+','.join('['+x+']' for x in spec['columns'])+' FROM analise_br.'+name);hashes=[]
   while True:
    batch=cur.fetchmany(10000)
    if not batch:break
    hashes.extend(row_hash(row,spec['kinds']) for row in batch)
   fingerprint=hashlib.sha256('\n'.join(sorted(hashes)).encode()).hexdigest();actual={'rows':len(hashes),'business_sha256':fingerprint,'query_and_check_seconds':time.monotonic()-started};record['tables'][name]=actual
   assert actual['rows']==spec['rows'] and fingerprint==spec['business_sha256'],(name,actual,spec)
   print('Full independent comparison passed',name,len(hashes),flush=True)
  record['source_publication']=before;assert before==results(cur.execute('SELECT * FROM gold_br.publication'))[0];record.update(status='analytics_full_comparison_passed',source_publication_unchanged=True,finished_at_utc=datetime.now(timezone.utc).isoformat());(out/'warehouse-verification.json').write_text(json.dumps(record,default=str,indent=2)+'\n')
print('Analytics deployment/verification finished',flush=True)
