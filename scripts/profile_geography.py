"""Sedes municipais oficiais do IBGE: coordenadas publicadas, sem geocodificacao fuzzy."""
import json,sqlite3,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
from scripts.download_sources import download
from fuelwatch.source import source_record

key='ibge_localidades_2022';url='https://geoftp.ibge.gov.br/organizacao_do_territorio/estrutura_territorial/localidades/Localidades_do_Brasil/2022/Localidades_Brasil_gpkg.zip'
try:record,payload=source_record(key)
except (FileNotFoundError,StopIteration):download(key,{'url':url,'filename':'localidades.zip'});record,payload=source_record(key)
folder=ROOT/'data/artifacts/context/geography';folder.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(ROOT/record['path']) as archive:
    names=[n for n in archive.namelist() if n.lower().endswith('.gpkg')];assert len(names)==1
    target=folder/'localidades.gpkg';target.write_bytes(archive.read(names[0]))
with sqlite3.connect('file:'+str(target.resolve())+'?mode=ro',uri=True) as cn:
    assert cn.execute('SELECT table_name,data_type,srs_id FROM gpkg_contents').fetchall()==[('BR_localidades_2022','features',4674)]
    f=pd.read_sql_query("SELECT CD_MUN AS municipio_ibge,NM_MUN AS municipio,SIGLA_UF AS uf,CT_LOCALIDADE AS categoria,SCT_LOCALIDADE AS subcategoria,LAT_LOCALIDADE AS latitude,LONG_LOCALIDADE AS longitude FROM BR_localidades_2022 WHERE (CT_LOCALIDADE='Cidade' AND SCT_LOCALIDADE IN ('Sede Municipal','Capital Federal')) OR CT_LOCALIDADE='Distrito Estadual de Fernando de Noronha'",cn)
assert not f.duplicated('municipio_ibge').any(),'Mais de uma sede municipal elegivel'
assert f['latitude'].between(-90,90).all() and f['longitude'].between(-180,180).all()
assert f['latitude'].notna().all() and f['longitude'].notna().all()
assert f['municipio_ibge'].str.fullmatch('[0-9]{7}').all()
reference=pd.read_parquet(ROOT/'data/artifacts/national/municipalities.parquet')
joined=reference.merge(f,on='municipio_ibge',how='left',validate='one_to_one',suffixes=('_ref','_geo'))
assert len(joined)==len(reference)
assert (joined.loc[joined.latitude.notna(),'uf_ref']==joined.loc[joined.latitude.notna(),'uf_geo']).all()
f.to_parquet(ROOT/'data/artifacts/context/municipal_seats.parquet',index=False)
report={'status':'official_municipal_geography_profiled_locally','fabric_executed':False,'source_url':url,'source_sha256':record['sha256'],'source_last_modified':record.get('last_modified'),'declared_dataset':'Localidades do Brasil 2022; snapshot oficial consultado na data registrada','crs':'EPSG:4674 SIRGAS 2000; latitude/longitude publicadas pelo IBGE','selection':'Cidade/Sede Municipal; Cidade/Capital Federal; Distrito Estadual de Fernando de Noronha. Capital Estadual duplicada excluida pela categoria, sem escolher coordenada arbitraria.','rows':len(f),'reference_municipalities':len(reference),'reference_missing_coordinates':int(joined.latitude.isna().sum()),'limits':'Sede municipal e ponto de referencia; nao e coordenada de posto, centroide do poligono ou garantia de representatividade meteorologica de todo o municipio.','checked_at_utc':datetime.now(timezone.utc).isoformat()}
(ROOT/'evidence/phase2/context/geography-profile.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:report[k] for k in ['rows','reference_municipalities','reference_missing_coordinates']}),flush=True)
