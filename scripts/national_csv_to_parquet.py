"""Converte o CSV real exportado em Parquet tipado; nao usa floats para precos."""
import csv,gzip,json,hashlib
from pathlib import Path
from datetime import date,datetime,timezone
from decimal import Decimal
import pyarrow as pa
import pyarrow.parquet as pq
import duckdb

root=Path.cwd();source=root/'data/processed/anp_brasil_2026_1.csv.gz';out=source.with_name('anp_brasil_2026_1.parquet');partial=out.with_suffix('.parquet.partial')
with gzip.open(source,'rt',encoding='utf-8-sig',newline='') as stream:
 reader=csv.DictReader(stream,delimiter=';');names=reader.fieldnames
 schema=pa.schema([pa.field(name,pa.date32() if name in {'data_coleta','inicio_semana_iso'} else pa.decimal128(10,3) if name=='preco_venda' else pa.bool_() if name in {'preco_incomum_iqr','iqr_avaliado'} else pa.string(),nullable=False) for name in names]);n=0;batch=[]
 with pq.ParquetWriter(partial,schema,compression='zstd') as writer:
  for row in reader:
   for name in ['data_coleta','inicio_semana_iso']:row[name]=date.fromisoformat(row[name])
   row['preco_venda']=Decimal(row['preco_venda'].replace(',','.'))
   for name in ['preco_incomum_iqr','iqr_avaliado']:
    assert row[name] in {'True','False','0','1'};row[name]=row[name] in {'True','1'}
   batch.append(row);n+=1
   if len(batch)==10000:writer.write_table(pa.Table.from_pylist(batch,schema=schema));batch=[]
  if batch:writer.write_table(pa.Table.from_pylist(batch,schema=schema))
assert n==422412
conn=duckdb.connect();conn.read_parquet(str(partial)).create_view('exported')
assert conn.execute('SELECT count(*),count(distinct cnpj),count(distinct municipio_ibge),count(distinct uf),count(distinct produto) FROM exported').fetchone()==(422412,7963,417,27,6)
assert conn.execute("SELECT count(*) FROM exported WHERE length(cnpj)<>14 OR (produto='GNV' AND unidade<>'m3') OR (produto<>'GNV' AND unidade<>'litro')").fetchone()[0]==0
m=json.loads((root/'data/artifacts/national/manifest.json').read_text(encoding='utf8'));actual=conn.execute('SELECT uf,produto,unidade,count(*) AS coletas,SUM(CAST(preco_venda*1000 AS bigint)) AS soma_mills FROM exported GROUP BY uf,produto,unidade').fetchall();expected={(r['uf'],r['produto'],r['unidade']):(r['coletas'],r['soma_mills']) for r in m['by_uf_product_unit']};assert all(expected[row[:3]]==row[3:] for row in actual);conn.close();partial.replace(out)
p=root/'evidence/fabric/national/export-verification.json';d=json.loads(p.read_text());d['parquet']={'file':out.relative_to(root).as_posix(),'rows':n,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'schema':str(schema),'roundtrip_counts_sums_cnpj_and_units_passed':True};d['parquet_verified_at_utc']=datetime.now(timezone.utc).isoformat();p.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d['parquet']))
