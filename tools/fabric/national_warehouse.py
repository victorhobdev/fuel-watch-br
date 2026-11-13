"""Publica Gold nacional no Warehouse apos validar o run exato e a Silver real."""
import argparse,json,re,time,uuid
from datetime import datetime,timezone
from azure.storage.filedatalake import DataLakeServiceClient
import pyodbc
from client import ROOT,request,credential
from warehouse import connect,results

p=argparse.ArgumentParser();p.add_argument('job_id');p.add_argument('--replay',action='store_true');args=p.parse_args()
c=json.loads((ROOT/'.local/fabric-environment.json').read_text());binding=json.loads((ROOT/'.local/national/fabric-binding.json').read_text());job=request('GET',f"workspaces/{c['workspace_id']}/items/{binding['notebook_id']}/jobs/instances/{args.job_id}").json();assert job['status']=='Completed',job
fs=DataLakeServiceClient('https://onelake.dfs.fabric.microsoft.com',credential=credential).get_file_system_client(c['workspace_id']);prefix=c['lakehouse_id']+'/Files/audit/national'
def utc(s):return datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=timezone.utc)
start,end=utc(job['startTimeUtc']),utc(job['endTimeUtc']);audits=[]
for path in fs.get_paths(path=prefix):
 if path.name.endswith('.json'):
  d=json.loads(fs.get_file_client(path.name).download_file().readall())
  if start<=utc(d['started_at_utc'])<=utc(d['finished_at_utc'])<=end:audits.append(d)
assert len(audits)==1 and audits[0]['status']=='national_silver_validated',audits
audit=audits[0];run=str(uuid.UUID(audit['run_id']));m=json.loads((ROOT/'data/artifacts/national/manifest.json').read_text(encoding='utf8'));assert audit['source_sha256']==m['anp']['sha256'] and audit['ibge_sha256']==m['ibge']['sha256']
folder=ROOT/'.local/national';(folder/('audit-'+run+'.json')).write_text(json.dumps(audit,indent=2));report={'run_id':run,'spark_job_id':args.job_id,'status':'started','replay':args.replay,'started_at_utc':datetime.now(timezone.utc).isoformat()};journal=folder/('warehouse-'+run+('-replay' if args.replay else '')+'.json');assert not journal.exists(),'Tentativa ja registrada: inspecionar antes de repetir publicacao'
fields='cnpj,cnpj_origem,produto,data_coleta,preco_venda,moeda,unidade,uf,municipio_ibge,municipio_origem,revenda_observada,bandeira_observada,preco_incomum_iqr';weekly='inicio_semana_iso,ano_iso,semana_iso,municipio_ibge,produto,moeda,unidade,coletas,postos_observados,soma_precos,preco_minimo,preco_maximo,precos_incomuns'
journal.write_text(json.dumps(report,indent=2))
with connect(c) as conn:
 cursor=conn.cursor()
 # Preflight de visibilidade antes de mudar qualquer objeto de negocio.
 for attempt in range(24):
  try:
   observed={}
   for table,expected in [('br_transfer_manifest',1),('silver_preco_brasil',m['counts']['accepted']),('ref_municipio_ibge_brasil',m['reference_municipalities']),('br_transfer_calendar',181),('br_expected_posto',m['station_versions']),('br_expected_weekly',m['weekly_groups'])]:
    n=cursor.execute('SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.'+table+' WHERE run_id=?',run).fetchone()[0];observed[table]=n
    if n!=expected:raise ValueError('Sync SQL endpoint: '+table+' '+str(n)+'/'+str(expected))
   break
  except (ValueError,pyodbc.ProgrammingError) as exc:
   if isinstance(exc,pyodbc.ProgrammingError) and not any(x in str(exc) for x in ['Invalid object name','42S02','208']):raise
   print('Waiting exact run SQL visibility',attempt+1,str(exc)[:160],flush=True)
   if attempt==23:raise
   time.sleep(15)
 report['source_tables_visible']=observed
 before=results(cursor.execute('SELECT COUNT_BIG(*) AS rows,SUM(preco_venda) AS sum_prices FROM gold.business_published'))[0][0];report['rj_baseline_before']=before
 for batch in re.split(r'(?m)^GO\s*$',(ROOT/'sql/national/01_schema.sql').read_text(encoding='utf8')):
  if batch.strip():results(cursor.execute(batch))
 for statement in (ROOT/'sql/national/02_views.sql').read_text(encoding='utf8').split('CREATE OR ALTER VIEW ')[1:]:results(cursor.execute('CREATE OR ALTER VIEW '+statement))
 results(cursor.execute((ROOT/'sql/national/03_publish.sql').read_text(encoding='utf8')))
 sql=f"""BEGIN TRY
 BEGIN TRANSACTION;
 IF (SELECT COUNT_BIG(*) FROM lh_fuelwatch.dbo.br_transfer_manifest WHERE run_id='{run}' AND source_sha256='{audit['source_sha256']}' AND ibge_sha256='{audit['ibge_sha256']}' AND expected_rows={m['counts']['accepted']})<>1
  THROW 51820,'Manifesto nacional nao aprovado.',1;
 DELETE FROM gold_br.stage_coleta;
 INSERT INTO gold_br.stage_coleta SELECT {fields} FROM lh_fuelwatch.dbo.silver_preco_brasil WHERE run_id='{run}';
 IF (SELECT COUNT_BIG(*) FROM gold_br.stage_coleta)<>{m['counts']['accepted']}
  THROW 51821,'Stage nacional incompleto.',1;
 DELETE FROM gold_br.stage_manifest;
 INSERT INTO gold_br.stage_manifest SELECT run_id,scope_id,source_sha256,ibge_sha256,silver_delta_version,CAST(0 AS bit),expected_rows,expected_stations,expected_municipalities,expected_unusual,'silver_preco_brasil',run_id FROM lh_fuelwatch.dbo.br_transfer_manifest WHERE run_id='{run}';
 DELETE FROM gold_br.expected_posto;
 INSERT INTO gold_br.expected_posto SELECT posto_sk,cnpj,revenda_observada,bandeira_observada,municipio_ibge,uf,observado_desde,observado_ate FROM lh_fuelwatch.dbo.br_expected_posto WHERE run_id='{run}';
 DELETE FROM gold_br.expected_weekly;
 INSERT INTO gold_br.expected_weekly SELECT {weekly} FROM lh_fuelwatch.dbo.br_expected_weekly WHERE run_id='{run}';
 COMMIT TRANSACTION;
 END TRY BEGIN CATCH IF @@TRANCOUNT>0 ROLLBACK TRANSACTION; THROW; END CATCH;
 """
 results(cursor.execute(sql));report['publication']=results(cursor.execute('EXEC gold_br.publish_gold @batch_id=?',run))
 totals=results(cursor.execute('SELECT COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos,COUNT(DISTINCT municipio_ibge) AS municipios,COUNT(DISTINCT uf) AS ufs,COUNT(DISTINCT produto) AS produtos FROM gold_br.business_published; SELECT COUNT_BIG(*) AS versions FROM gold_br.dim_posto; SELECT COUNT_BIG(*) AS groups FROM gold_br.preco_semanal;'))
 assert totals[0][0]=={'coletas':422412,'postos':7963,'municipios':417,'ufs':27,'produtos':6},totals
 assert totals[1][0]['versions']==8159 and totals[2][0]['groups']==50965
 distribution=results(cursor.execute('SELECT uf,produto,moeda,unidade,COUNT_BIG(*) AS coletas,COUNT(DISTINCT cnpj) AS postos,COUNT(DISTINCT municipio_ibge) AS municipios,SUM(CAST(preco_venda*1000 AS bigint)) AS soma_mills,SUM(CAST(preco_incomum_iqr AS bigint)) AS incomuns FROM gold_br.business_published GROUP BY uf,produto,moeda,unidade'))[0]
 assert sorted(distribution,key=lambda x:(x['uf'],x['produto']))==sorted(m['by_uf_product_unit'],key=lambda x:(x['uf'],x['produto'])),'Perfil por UF/produto/unidade divergiu'
 after=results(cursor.execute('SELECT COUNT_BIG(*) AS rows,SUM(preco_venda) AS sum_prices FROM gold.business_published'))[0][0];assert before==after
 report.update(status='national_warehouse_validated',totals=totals,by_uf_product_unit=distribution,full_scd2_and_weekly_comparison_passed=True,full_silver_gold_business_comparison_passed=True,rj_baseline_unchanged=True,silver_audit=audit,finished_at_utc=datetime.now(timezone.utc).isoformat())
journal.write_text(json.dumps(report,default=str,indent=2));out=ROOT/'evidence/fabric/national'/run;out.mkdir(parents=True,exist_ok=True);(out/('warehouse-replay.json' if args.replay else 'warehouse-verification.json')).write_text(json.dumps(report,default=str,indent=2)+'\n');(out/'silver-verification.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps({'status':report['status'],'run_id':run,'totals':totals,'replay':args.replay}),flush=True)
