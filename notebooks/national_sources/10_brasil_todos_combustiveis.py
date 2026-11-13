"""Spark nacional: validacao distribuida e publicacao Delta; nao altera o baseline RJ."""
import hashlib,json,sys,uuid
from pathlib import Path
from datetime import datetime,timezone
from pyspark.sql import functions as F

files_root=Path('/lakehouse/default/Files')
bundle=files_root/p_bundle_relative_path
manifest_bytes=(bundle/'manifest.json').read_bytes()
assert hashlib.sha256(manifest_bytes).hexdigest()==p_manifest_sha256
manifest=json.loads(manifest_bytes)
for name,spec in manifest['files'].items():
 payload=(bundle/name).read_bytes()
 assert len(payload)==spec['bytes'] and hashlib.sha256(payload).hexdigest()==spec['sha256'],name
spark.sparkContext.addPyFile(str(bundle/'fuelwatch_national_rules.zip'))
spark.conf.set('spark.sql.session.timeZone','UTC')
from fuelwatch.national import national_reference,IQR_KEYS
from fuelwatch.m02_reference import BUSINESS_FIELDS,RAW_COLUMNS
from fuelwatch.silver_spark import classify,category_counts,compare_business
rows,lookup=national_reference(json.loads((bundle/'municipios.json').read_bytes()),json.loads((bundle/'estados.json').read_bytes()))
run_id=str(uuid.uuid4());audit={'run_id':run_id,'environment':'fabric','scope':manifest['scope'],'status':'started','started_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':manifest['anp']['sha256'],'ibge_sha256':manifest['ibge']['sha256'],'spark_version':spark.version,'manifest_sha256':p_manifest_sha256}
parts=None;accepted=None

def path(name):return 'Files/'+p_bundle_relative_path+'/'+name

def lineage(df):
 return (df.withColumn('scope_id',F.lit(manifest['scope']['scope_id'])).withColumn('source_sha256',F.lit(audit['source_sha256'])).withColumn('ibge_sha256',F.lit(audit['ibge_sha256'])).withColumn('contract_version',F.lit(manifest['scope']['contract_version'])).withColumn('run_id',F.lit(run_id)).withColumn('ingested_at_utc',F.lit(audit['started_at_utc'])).withColumn('is_synthetic',F.lit(False)))

try:
 bronze=spark.table('bronze_anp').where(F.col('source_sha256')==audit['source_sha256'])
 assert bronze.count()==manifest['anp']['rows']
 parts=classify(bronze,lookup,manifest['scope']);counts=category_counts(parts)
 assert counts=={'selected':manifest['counts']['received'],'invalid':manifest['counts']['invalid'],'exact_duplicate_excess':manifest['counts']['exact_duplicate_excess'],'conflicting_rows_after_exact_dedup':manifest['counts']['conflicting_rows'],'accepted':manifest['counts']['accepted']},counts
 for category,table in [('invalid','quarantine_preco_brasil'),('duplicates','audit_duplicatas_brasil'),('conflicts','audit_conflitos_brasil')]:
  lineage(parts[category]).write.format('delta').mode('append').saveAsTable(table)
 assert counts['conflicting_rows_after_exact_dedup']==0
 base=parts['accepted'].withColumn('inicio_semana_iso',F.to_date(F.date_trunc('week','data_coleta'))).withColumn('price_mills',(F.col('preco_venda')*1000).cast('long'))
 bounds=base.groupBy(*IQR_KEYS).agg(F.count('*').alias('coletas'),F.countDistinct('cnpj').alias('postos'),F.expr('percentile(price_mills,array(0.25D,0.75D))').alias('q'))
 bounds=(bounds.withColumn('q25_mills',F.col('q')[0]).withColumn('q75_mills',F.col('q')[1]).withColumn('iqr_lower_mills',F.col('q25_mills')-1.5*(F.col('q75_mills')-F.col('q25_mills'))).withColumn('iqr_upper_mills',F.col('q75_mills')+1.5*(F.col('q75_mills')-F.col('q25_mills'))).withColumn('iqr_avaliado',(F.col('coletas')>=20)&(F.col('postos')>=5)).drop('q'))
 accepted=(base.join(bounds,IQR_KEYS,'inner').withColumn('preco_incomum_iqr',F.col('iqr_avaliado')&~F.col('price_mills').between(F.col('iqr_lower_mills'),F.col('iqr_upper_mills'))).cache())
 expected=spark.read.parquet(path('reference.parquet')).withColumn('preco_venda',F.col('preco_venda').cast('decimal(10,3)'))
 compare_business(expected,accepted)
 assert accepted.count()==manifest['counts']['accepted']
 assert accepted.where('preco_incomum_iqr').count()==manifest['unusual']
 assert accepted.where('NOT iqr_avaliado').count()==manifest['iqr_not_evaluated_rows']
 assert accepted.select('cnpj').distinct().count()==manifest['stations']
 assert accepted.select('municipio_ibge').distinct().count()==manifest['municipalities']
 assert accepted.select('uf').distinct().count()==27 and accepted.select('produto').distinct().count()==6
 observed_attrs=accepted.select('cnpj','data_coleta','revenda_observada','bandeira_observada','municipio_ibge','uf').distinct()
 assert observed_attrs.groupBy('cnpj','data_coleta').count().where('count>1').limit(1).count()==0
 previous_version=None
 if spark.catalog.tableExists('silver_preco_brasil'):
  previous_version=int(spark.sql('DESCRIBE HISTORY silver_preco_brasil').agg(F.max('version')).first()[0]);compare_business(spark.table('silver_preco_brasil'),accepted)
 # Os campos de endereco continuam disponiveis sem perder o JSON original.
 raw=parts['classified'].select('raw_row_sha256','regiao_sigla','nome_rua','numero_rua','complemento','bairro','cep','valor_compra').dropDuplicates(['raw_row_sha256'])
 enriched=accepted.join(raw,'raw_row_sha256','inner').drop('price_mills')
 enriched=enriched.withColumn('cep_normalizado',F.when(F.length(F.regexp_replace('cep',r'\D',''))==8,F.regexp_replace('cep',r'\D',''))).withColumn('valor_compra_tipado',F.expr("try_cast(replace(nullif(valor_compra,''),',','.') as decimal(10,3))"))
 candidate=lineage(enriched)
 candidate.write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('silver_preco_brasil')
 actual=spark.table('silver_preco_brasil');compare_business(expected,actual)
 assert actual.count()==manifest['counts']['accepted']
 version=int(spark.sql('DESCRIBE HISTORY silver_preco_brasil').agg(F.max('version')).first()[0])
 reference=lineage(spark.read.parquet(path('municipalities.parquet')))
 reference.write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('ref_municipio_ibge_brasil')
 lineage(bounds).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('ref_limites_iqr_brasil')
 for filename,table in [('calendar.parquet','br_transfer_calendar'),('history.parquet','br_expected_posto'),('weekly.parquet','br_expected_weekly')]:
  frame=spark.read.parquet(path(filename))
  for col in ['soma_precos','preco_minimo','preco_maximo']:
   if col in frame.columns:frame=frame.withColumn(col,F.col(col).cast('decimal(18,3)'))
  frame.withColumn('run_id',F.lit(run_id)).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable(table)
 # Manifesto por ultimo: Warehouse somente admite este run e contagens completas.
 summary={'run_id':run_id,'scope_id':manifest['scope']['scope_id'],'source_sha256':audit['source_sha256'],'ibge_sha256':audit['ibge_sha256'],'silver_delta_version':version,'expected_rows':manifest['counts']['accepted'],'expected_stations':manifest['stations'],'expected_municipalities':manifest['municipalities'],'expected_history':manifest['station_versions'],'expected_weekly':manifest['weekly_groups'],'expected_unusual':manifest['unusual']}
 spark.createDataFrame([summary]).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('br_transfer_manifest')
 audit.update(summary);audit.update(status='national_silver_validated',counts=counts,ufs=27,products=6,previous_delta_version=previous_version,same_business_as_previous=previous_version is not None,full_business_comparison_passed=True,iqr_not_evaluated_rows=manifest['iqr_not_evaluated_rows'])
except Exception as exc:
 audit.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1500]);raise
finally:
 if parts is not None:parts['classified'].unpersist()
 if accepted is not None:accepted.unpersist()
 audit['finished_at_utc']=datetime.now(timezone.utc).isoformat();folder=files_root/'audit/national';folder.mkdir(parents=True,exist_ok=True);(folder/(run_id+'.json')).write_text(json.dumps(audit,indent=2),encoding='utf8')
print(json.dumps(audit),flush=True)
notebookutils.notebook.exit(json.dumps(audit))
