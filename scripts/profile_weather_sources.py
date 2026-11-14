"""Preservar arquivos anuais INMET e inspecionar amostra antes do tratamento."""
import csv,hashlib,io,json,shutil,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_sources import download

out=ROOT/'evidence/phase2/context';out.mkdir(parents=True,exist_ok=True)
profiles=[]
for year in [2024,2025,2026]:
    key='inmet_'+str(year);url=f'https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip'
    log=ROOT/'data/manifest/downloads.jsonl'
    records=[json.loads(line) for line in log.read_text(encoding='utf8').splitlines()]
    record=next((r for r in reversed(records) if r['source_id']==key and r['status'] in ['downloaded','identical_content']),None)
    if record is None:
        assert shutil.disk_usage(ROOT).free>3*1024**3,'Espaco insuficiente para preservar fontes meteorologicas'
        print('Downloading official annual INMET archive',year,flush=True)
        record=download(key,{'url':url,'filename':str(year)+'.zip'})
    path=ROOT/record['path']
    with path.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==record['sha256']
    with zipfile.ZipFile(path) as archive:
        members=[m for m in archive.infolist() if not m.is_dir() and m.filename.lower().endswith('.csv')]
        assert members,'ZIP sem CSV de estacoes'
        sample=sorted(members,key=lambda m:m.filename)[0]
        payload=archive.read(sample)
        try:text=payload.decode('utf-8-sig');encoding='utf-8-sig'
        except UnicodeDecodeError:text=payload.decode('latin1');encoding='latin1'
        lines=list(csv.reader(io.StringIO(text),delimiter=';'))
        # O perfil registra o layout real antes de impor um parser para todos os arquivos.
        header=next(i for i,row in enumerate(lines) if any('UTC' in value.upper() for value in row) and len(row)>10)
        profile={'year':year,'source_url':url,'source_sha256':record['sha256'],'source_bytes':record['bytes'],'source_last_modified':record.get('last_modified'),'csv_members':len(members),'total_uncompressed_bytes':sum(m.file_size for m in members),'sample_member':sample.filename,'sample_encoding':encoding,'sample_metadata_rows':lines[:header],'sample_header':lines[header],'sample_rows':lines[header+1:header+5],'sample_data_rows':len(lines)-header-1,'fabric_executed':False,'checked_at_utc':datetime.now(timezone.utc).isoformat()}
        (out/(key+'-profile.json')).write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        profiles.append(profile)
        print(json.dumps({k:profile[k] for k in ['year','source_bytes','csv_members','sample_encoding','sample_data_rows']}),flush=True)
(out/'weather-source-profiles.json').write_text(json.dumps({'status':'official_weather_archives_preserved_and_sampled','fabric_executed':False,'profiles':profiles},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
