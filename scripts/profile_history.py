"""Descobrir, preservar e perfilar os quatro semestres historicos oficiais."""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_sources import download
from fuelwatch.source import source_record, read_anp

INDEX = 'https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/serie-historica-de-precos-de-combustiveis'
parser = argparse.ArgumentParser()
parser.add_argument('--refresh', action='store_true', help='Rebaixar tambem arquivos antigos para detectar republicacao')
args = parser.parse_args()
out = ROOT / 'evidence/phase2/history'
out.mkdir(parents=True, exist_ok=True)
with urllib.request.urlopen(INDEX, timeout=60) as response:
    page = response.read()
page_sha = hashlib.sha256(page).hexdigest()
snapshot = ROOT / 'data/raw/anp_catalog' / page_sha / 'index.html'
snapshot.parent.mkdir(parents=True, exist_ok=True)
if snapshot.exists():
    assert snapshot.read_bytes() == page
else:
    snapshot.write_bytes(page)
links = sorted(set(re.findall(r'https://www\.gov\.br/anp/[^"<>\s]+/ca/ca-(?:2024|2025)-0[12]\.zip', page.decode('utf8'))))
assert len(links) == 4, 'Catalogo oficial nao contem os quatro semestres esperados'
discovery = {'index_url': INDEX, 'index_sha256': page_sha, 'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'official_urls': links}
(out/'discovery.json').write_text(json.dumps(discovery, indent=2)+'\n', encoding='utf8')
profiles = []
for url in links:
    match = re.search(r'ca-(\d{4})-0([12])\.zip$', url)
    year, semester = map(int, match.groups())
    source_id = f'anp_{year}_{semester}'
    try:
        record, payload = source_record(source_id)
    except (FileNotFoundError, StopIteration):
        record = None
    if args.refresh or record is None:
        record = download(source_id, {'url':url, 'filename':url.rsplit('/',1)[-1]})
        record, payload = source_record(source_id)
    frame, meta = read_anp(payload)
    import pandas as pd
    dates = pd.to_datetime(frame['Data da Coleta'], format='%d/%m/%Y', errors='coerce')
    start, end = (f'{year}-01-01', f'{year}-06-30') if semester == 1 else (f'{year}-07-01', f'{year}-12-31')
    empty = frame.eq('').all(axis=1)
    invalid_dates = ~empty & (dates.isna() | ~dates.between(start,end))
    keys = ['CNPJ da Revenda','Produto','Data da Coleta','Unidade de Medida']
    nonempty = frame.loc[~empty]
    unique = nonempty.drop_duplicates()
    conflicting = unique.duplicated(keys, keep=False)
    prices = pd.to_numeric(frame['Valor de Venda'].str.replace(',','.',regex=False), errors='coerce')
    profile = {'source_id':source_id, 'source_url':url, 'source_sha256':record['sha256'], 'source_bytes':record['bytes'],
        'declared_period':{'start':start,'end':end}, 'layout':frame.columns.tolist(), **meta,
        'rows':len(frame),'empty_records':int(empty.sum()),'invalid_dates_nonempty':int(invalid_dates.sum()),
        'exact_duplicate_excess':len(nonempty)-len(unique),'conflicting_key_rows':int(conflicting.sum()),
        'candidate_business_key':keys,'date_min':dates.min().date().isoformat(),'date_max':dates.max().date().isoformat(),
        'invalid_nonpositive_prices':int((~empty & (prices.isna() | (prices <= 0))).sum()),
        'ufs':sorted(nonempty['Estado - Sigla'].unique().tolist()),'stations':int(nonempty['CNPJ da Revenda'].nunique()),
        'observed_months':sorted(dates.dropna().dt.strftime('%Y-%m').unique().tolist()),
        'products_units':frame.groupby(['Produto','Unidade de Medida']).size().reset_index(name='rows').to_dict(orient='records'),
        'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'fabric_executed':False}
    assert len(profile['observed_months']) == 6
    (out/(source_id+'-profile.json')).write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    profiles.append(profile)
    print(json.dumps({k:profile[k] for k in ['source_id','rows','exact_duplicate_excess','conflicting_key_rows','invalid_nonpositive_prices','date_min','date_max']},ensure_ascii=True),flush=True)
(out/'profile-summary.json').write_text(json.dumps({'status':'four_historical_sources_profiled_locally','profiles':profiles},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
