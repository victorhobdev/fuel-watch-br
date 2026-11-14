"""Descoberta oficial com revisao por hash de semestres antigos, sem autopromocao."""
import argparse,hashlib,json,re,sys,urllib.request,uuid
from datetime import date,datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_sources import download
p=argparse.ArgumentParser();p.add_argument('--refresh',action='store_true');args=p.parse_args()
policy=json.loads((ROOT/'config/refresh-policy.json').read_text());started=datetime.now(timezone.utc).isoformat();run_id=str(uuid.uuid4())
with urllib.request.urlopen(policy['catalog_url'],timeout=60) as response:page=response.read()
sha=hashlib.sha256(page).hexdigest();snapshot=ROOT/'data/raw/anp_catalog'/sha/'index.html';snapshot.parent.mkdir(parents=True,exist_ok=True)
if snapshot.exists():assert snapshot.read_bytes()==page
else:snapshot.write_bytes(page)
urls=sorted(set(re.findall(r'https://www\.gov\.br/anp/[^"<>\s]+/ca/ca-20\d{2}-0[12]\.zip',page.decode('utf8'))))
records=[json.loads(line) for line in (ROOT/'data/manifest/downloads.jsonl').read_text(encoding='utf8').splitlines()]
known={r['source_id']:r for r in records if r['status'] in ['downloaded','identical_content']}
approved={s['source_id']:s['source_sha256'] for s in json.loads((ROOT/'evidence/phase2/history/reference-summary.json').read_text(encoding='utf8'))['sources']}
approved['anp_2026_1']=json.loads((ROOT/'data/artifacts/national/manifest.json').read_text(encoding='utf8'))['anp']['sha256']
sources=[]
for url in urls:
    match=re.search(r'ca-(\d{4})-0([12])\.zip$',url);year,semester=map(int,match.groups())
    if year<policy['first_year']:continue
    start=date(year,1 if semester==1 else 7,1);end=date(year,6,30) if semester==1 else date(year,12,31)
    if policy['only_closed_semesters'] and end>=date.today():continue
    key=f'anp_{year}_{semester}';old=known.get(key)
    current=download(key,{'url':url,'filename':url.rsplit('/',1)[-1]}) if args.refresh else old
    actual_sha=current['sha256'] if current else None
    status='catalog_only' if not args.refresh else 'new_delivery' if old is None else 'identical_content' if old['sha256']==actual_sha else 'republication_candidate'
    sources.append({'source_id':key,'source_url':url,'date_start':start.isoformat(),'date_end':end.isoformat(),'classification':status,'previous_sha256':old['sha256'] if old else None,'observed_sha256':actual_sha,'approved_sha256':approved.get(key),'matches_approved_version':actual_sha is not None and actual_sha==approved.get(key),'download_run_id':current['run_id'] if args.refresh else None,'downloaded_bytes':current['bytes'] if args.refresh else 0})
    print(key,status,'approved='+str(sources[-1]['matches_approved_version']),flush=True)
assert sources,'Nenhum semestre elegivel foi encontrado no catalogo oficial'
report={'status':'official_catalog_and_old_versions_refreshed' if args.refresh else 'official_catalog_discovered_only','run_id':run_id,'files_fetched':args.refresh,'catalog_sha256':sha,'policy':policy,'sources':sources,'total_downloaded_bytes':sum(x['downloaded_bytes'] for x in sources),'publication_changed':False,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat()}
out=ROOT/'evidence/phase2/refresh';out.mkdir(parents=True,exist_ok=True)
(out/('discovery-'+run_id+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Discovery receipt',run_id,flush=True)
