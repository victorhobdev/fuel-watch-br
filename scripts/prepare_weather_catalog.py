"""Catalogo anual INMET e associacao geografica definida antes da analise de precos."""
import csv,io,json,math,re,zipfile
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1]
policy=json.loads((root/'config/weather.json').read_text())
records=[json.loads(line) for line in (root/'data/manifest/downloads.jsonl').read_text(encoding='utf8').splitlines()]
stations=[]
for year in [2024,2025,2026]:
    source=next(r for r in reversed(records) if r['source_id']=='inmet_'+str(year) and r['status'] in ['downloaded','identical_content'])
    with zipfile.ZipFile(root/source['path']) as archive:
        for member in archive.infolist():
            if member.is_dir() or not member.filename.lower().endswith('.csv'):continue
            with archive.open(member) as stream:raw=b''.join(stream.readline() for _ in range(9))
            try:text=raw.decode('utf-8-sig');encoding='utf-8-sig'
            except UnicodeDecodeError:text=raw.decode('latin1');encoding='latin1'
            lines=list(csv.reader(io.StringIO(text),delimiter=';'));assert len(lines)==9
            meta={row[0].strip().rstrip(':'):row[1].strip() for row in lines[:8]}
            assert 'CODIGO (WMO)' in meta and 'LATITUDE' in meta and 'LONGITUDE' in meta
            code=meta['CODIGO (WMO)'];assert re.fullmatch('[A-Z][0-9]{3}',code),code
            latitude=float(meta['LATITUDE'].replace(',','.'));longitude=float(meta['LONGITUDE'].replace(',','.'))
            valid=math.isfinite(latitude) and math.isfinite(longitude) and -90<=latitude<=90 and -180<=longitude<=180
            stations.append({'year':year,'station_id':code,'station_name':meta['ESTACAO'],'uf':meta['UF'],'latitude':latitude,'longitude':longitude,'valid_coordinates':valid,'foundation_date_raw':meta.get('DATA DE FUNDACAO'),'encoding':encoding,'member':member.filename,'source_sha256':source['sha256']})
f=pd.DataFrame(stations)
assert not f.duplicated(['year','station_id']).any(),'Arquivos sobrepostos para estacao/ano exigem conciliacao'
seats=pd.read_parquet(root/'data/artifacts/context/municipal_seats.parquet')
observed=pd.read_parquet(root/'data/artifacts/history/publication/reference.parquet',columns=['municipio_ibge','data_coleta'])
observed['year']=pd.to_datetime(observed['data_coleta']).dt.isocalendar().year.astype(int)
municipal_years=observed[['municipio_ibge','year']].drop_duplicates().merge(seats,on='municipio_ibge',how='left',validate='many_to_one')
def distance(lat1,lon1,lat2,lon2):
    a1,a2=math.radians(lat1),math.radians(lat2);dlat=a2-a1;dlon=math.radians(lon2-lon1)
    a=math.sin(dlat/2)**2+math.cos(a1)*math.cos(a2)*math.sin(dlon/2)**2
    return 2*6371*math.asin(math.sqrt(min(1,max(0,a))))
displacement={}
for code,group in f.loc[f.valid_coordinates].groupby('station_id'):
    points=list(zip(group.latitude,group.longitude))
    displacement[code]=max(distance(*a,*b) for a in points for b in points)
f['maximum_coordinate_change_km']=f.station_id.map(displacement)
f['stable_coordinates']=f.maximum_coordinate_change_km.le(policy['maximum_station_coordinate_change_km'])
f.to_parquet(root/'data/artifacts/context/station_catalog.parquet',index=False)
associations=[]
for m in municipal_years.to_dict(orient='records'):
    candidates=f.loc[(f.year==m['year'])&f.valid_coordinates&f.stable_coordinates].to_dict(orient='records')
    ranked=sorted((distance(m['latitude'],m['longitude'],s['latitude'],s['longitude']),s['station_id']) for s in candidates)
    nearest_km,nearest=ranked[0]
    eligible=nearest_km<=policy['maximum_distance_km']
    associations.append({'municipio_ibge':m['municipio_ibge'],'year':m['year'],'station_id':nearest if eligible else None,'nearest_station_id':nearest,'distance_km':nearest_km,'association_status':'associated' if eligible else 'beyond_maximum_distance','municipal_latitude':m['latitude'],'municipal_longitude':m['longitude']})
a=pd.DataFrame(associations);assert len(a)==len(municipal_years) and not a.duplicated(['municipio_ibge','year']).any()
a.to_parquet(root/'data/artifacts/context/station_associations.parquet',index=False)
report={'status':'annual_station_catalog_and_associations_prepared_locally','fabric_executed':False,'policy':policy,'station_year_records':len(f),'invalid_station_coordinates':int((~f.valid_coordinates).sum()),'station_ids_excluded_coordinate_change':int(f.loc[~f.stable_coordinates,'station_id'].nunique()),'municipality_years':len(a),'by_year':a.groupby(['year','association_status']).size().reset_index(name='municipalities').to_dict(orient='records'),'maximum_selected_distance_km':float(a.loc[a.station_id.notna(),'distance_km'].max()),'checked_at_utc':datetime.now(timezone.utc).isoformat()}
(root/'evidence/phase2/context/station-associations-local.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['station_year_records','municipality_years','by_year','maximum_selected_distance_km']}),flush=True)
