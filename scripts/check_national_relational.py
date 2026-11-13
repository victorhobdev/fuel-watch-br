import duckdb,re,json
from pathlib import Path
c=duckdb.connect();c.execute('CREATE SCHEMA gold_br');c.execute('CREATE MACRO DATALENGTH(x) AS octet_length(encode(x))')
schema=Path('sql/national/01_schema.sql').read_text(encoding='utf8')
for s in re.findall(r'CREATE TABLE gold_br\.\w+ \([\s\S]*?\n\);',schema):c.execute(re.sub(r'\bbit\b','BOOLEAN',s,flags=re.I).replace('datetime2(6)','TIMESTAMP'))
v=Path('sql/national/02_views.sql').read_text(encoding='utf8').replace('CREATE OR ALTER VIEW','CREATE OR REPLACE VIEW').replace('CONVERT(varchar(10), data_coleta, 23)','CAST(data_coleta AS varchar(10))').replace('COUNT_BIG(*)','COUNT(*)');v=re.sub(r'CAST\((\w+) AS varbinary\(8000\)\)',r'encode(\1)',v);c.execute(v)
c.execute("INSERT INTO gold_br.stage_coleta BY NAME SELECT * FROM read_parquet('data/artifacts/national/reference.parquet')")
c.execute("INSERT INTO gold_br.dim_data BY NAME SELECT * FROM read_parquet('data/artifacts/national/calendar.parquet')")
c.execute("INSERT INTO gold_br.dim_municipio SELECT municipio_ibge,nome,uf FROM read_parquet('data/artifacts/national/municipalities.parquet')")
c.execute('INSERT INTO gold_br.dim_produto SELECT CAST(DENSE_RANK() OVER (ORDER BY produto,moeda,unidade) AS INTEGER),produto,moeda,unidade FROM (SELECT DISTINCT produto,moeda,unidade FROM gold_br.stage_coleta) p')
c.execute('INSERT INTO gold_br.dim_posto SELECT * FROM gold_br.candidate_posto');c.execute("INSERT INTO gold_br.fato_preco_coletado SELECT *, 'local-test' FROM gold_br.candidate_fato")
assert c.execute('SELECT COUNT(*) FROM gold_br.business_published').fetchone()[0]==422412
for actual,file,columns in [('dim_posto','history.parquet','*'),('preco_semanal','weekly.parquet','inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns')]:
 q=f"SELECT {columns} FROM gold_br.{actual}";ref=f"SELECT * FROM read_parquet('data/artifacts/national/{file}')";assert c.execute(f'SELECT COUNT(*) FROM (({q}) EXCEPT ({ref}))').fetchone()[0]==0;assert c.execute(f'SELECT COUNT(*) FROM (({ref}) EXCEPT ({q}))').fetchone()[0]==0
r={'status':'national_relational_reference_passed','environment':'local_duckdb_not_fabric','coletas':422412,'station_versions':8159,'weekly_groups':50965,'products':6,'full_history_and_weekly_equal':True};Path('.local/national/relational-local.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
