"""Candidato historico conjunto: IQR, transferencia e manifesto protegido."""
import hashlib,json,uuid
from pathlib import Path
from datetime import datetime,timezone
from functools import reduce
from pyspark.sql import functions as F

files=Path('/lakehouse/default/Files');bundle=files/p_bundle_relative_path
raw=(bundle/'manifest.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==p_manifest_sha256
m=json.loads(raw)
for name,spec in m['files'].items():
    content=(bundle/name).read_bytes();assert len(content)==spec['bytes'] and hashlib.sha256(content).hexdigest()==spec['sha256'],name
spark.sparkContext.addPyFile(str(bundle/'rules.zip'))
from fuelwatch.m02_reference import TYPED_FIELDS,BUSINESS_FIELDS
from fuelwatch.national import IQR_KEYS
spark.conf.set('spark.sql.session.timeZone','UTC')
assert p_fault_stage in ['none','after_silver']
run_id=str(uuid.uuid4());accepted=None
audit={'run_id':run_id,'environment':'fabric','status':'started','started_at_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':p_manifest_sha256,'fault_stage':p_fault_stage,'sources':m['sources']}
def path(name):return 'Files/'+p_bundle_relative_path+'/'+name
def stamp(df):return df.withColumn('run_id',F.lit(run_id)).withColumn('is_synthetic',F.lit(False))
def compare(a,b):
    a=a.select(*BUSINESS_FIELDS);b=b.select(*BUSINESS_FIELDS)
    assert a.schema==b.schema,'Schema de negocio diverge'
    assert a.exceptAll(b).limit(1).count()==0 and b.exceptAll(a).limit(1).count()==0,'Negocio diverge'
try:
    frames=[]
    for source in m['sources']:
        if source['source_id']=='anp_2026_1':
            f=spark.table('silver_preco_brasil').where(F.col('source_sha256')==source['source_sha256']).withColumn('source_id',F.lit(source['source_id']))
        else:
            f=spark.table('hist_silver_versoes').where((F.col('source_id')==source['source_id'])&(F.col('source_sha256')==source['source_sha256']))
        assert f.count()==source['counts']['accepted'],source['source_id']
        frames.append(f.select(*TYPED_FIELDS,'source_id','source_sha256'))
    base=reduce(lambda a,b:a.unionByName(b),frames)
    assert base.groupBy('cnpj','produto','data_coleta','unidade').count().where('count>1').limit(1).count()==0
    base=base.withColumn('inicio_semana_iso',F.to_date(F.date_trunc('week','data_coleta'))).withColumn('price_mills',(F.col('preco_venda')*1000).cast('long'))
    bounds=base.groupBy(*IQR_KEYS).agg(F.count('*').alias('coletas'),F.countDistinct('cnpj').alias('postos'),F.expr('percentile(price_mills,array(0.25D,0.75D))').alias('q'))
    bounds=(bounds.withColumn('q25_mills',F.col('q')[0]).withColumn('q75_mills',F.col('q')[1]).withColumn('iqr_lower_mills',F.col('q25_mills')-1.5*(F.col('q75_mills')-F.col('q25_mills'))).withColumn('iqr_upper_mills',F.col('q75_mills')+1.5*(F.col('q75_mills')-F.col('q25_mills'))).withColumn('iqr_avaliado',(F.col('coletas')>=20)&(F.col('postos')>=5)).drop('q'))
    accepted=base.join(bounds,IQR_KEYS,'inner').withColumn('preco_incomum_iqr',F.col('iqr_avaliado')&~F.col('price_mills').between(F.col('iqr_lower_mills'),F.col('iqr_upper_mills'))).cache()
    expected=spark.read.parquet(path('reference.parquet')).withColumn('preco_venda',F.col('preco_venda').cast('decimal(10,3)'))
    compare(expected,accepted)
    assert accepted.count()==m['rows']
    assert accepted.where('preco_incomum_iqr').count()==m['unusual']
    assert accepted.where('NOT iqr_avaliado').count()==m['iqr_not_evaluated_rows']
    stamp(accepted.drop('price_mills')).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('hist_transfer_coletas')
    compare(expected,spark.table('hist_transfer_coletas'))
    print('Joint historical Silver candidate reconciled',m['rows'],flush=True)
    if p_fault_stage=='after_silver':raise RuntimeError('HISTORY_INJECTED_AFTER_SILVER: manifesto nao promovido')
    stamp(bounds).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('hist_transfer_iqr')
    for filename,table in [('calendar.parquet','hist_transfer_calendar'),('history.parquet','hist_expected_posto'),('weekly.parquet','hist_expected_weekly'),('municipalities.parquet','hist_transfer_municipio')]:
        f=spark.read.parquet(path(filename))
        for column in ['soma_precos','preco_minimo','preco_maximo']:
            if column in f.columns:f=f.withColumn(column,F.col(column).cast('decimal(18,3)'))
        stamp(f).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable(table)
    delta_version=int(spark.sql('DESCRIBE HISTORY hist_transfer_coletas').agg(F.max('version')).first()[0])
    manifest_row={'run_id':run_id,'source_snapshot_sha256':p_manifest_sha256,'ibge_sha256':m['ibge_sha256'],'silver_delta_version':delta_version,'expected_rows':m['rows'],'expected_stations':m['stations'],'expected_municipalities':m['municipalities'],'expected_unusual':m['unusual'],'expected_calendar_days':m['calendar_days'],'expected_products':m['products'],'date_start':m['date_start'],'date_end':m['date_end']}
    # Ultima escrita: o consumidor exige o run exato em todas as tabelas.
    stamp(spark.createDataFrame([manifest_row])).write.format('delta').mode('overwrite').option('overwriteSchema','true').saveAsTable('hist_transfer_manifest')
    audit.update(status='historical_publication_candidate_validated',rows=m['rows'],full_business_comparison_passed=True,delta_version=delta_version)
except Exception as exc:
    audit.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1500]);raise
finally:
    if accepted is not None:accepted.unpersist()
    audit['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    target=files/'audit/history-publication';target.mkdir(parents=True,exist_ok=True)
    (target/(run_id+'.json')).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(audit),flush=True)
notebookutils.notebook.exit(json.dumps(audit))
