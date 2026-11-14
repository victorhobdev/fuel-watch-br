"""Versoes historicas ANP: Bronze preservada e Silver tipada por arquivo."""
import csv, hashlib, io, json, re, uuid, zipfile
from pathlib import Path
from datetime import datetime, timezone
from pyspark.sql import functions as F, types as T

files=Path('/lakehouse/default/Files')
assert re.fullmatch('[0-9a-f]{64}',p_manifest_sha256)
assert re.fullmatch('[0-9a-f-]{36}',p_landing_run_id)
bundle=files/p_bundle_relative_path
payload=(bundle/'manifest.json').read_bytes()
assert hashlib.sha256(payload).hexdigest()==p_manifest_sha256
manifest=json.loads(payload)
for name,spec in manifest['files'].items():
    content=(bundle/name).read_bytes()
    assert hashlib.sha256(content).hexdigest()==spec['sha256'] and len(content)==spec['bytes'],name
spark.sparkContext.addPyFile(str(bundle/'rules.zip'))
from fuelwatch.national import national_reference
from fuelwatch.m02_reference import RAW_COLUMNS, HEADERS, TYPED_FIELDS
from fuelwatch.silver_spark import classify,category_counts
_,lookup=national_reference(json.loads((bundle/'municipios.json').read_bytes()),json.loads((bundle/'estados.json').read_bytes()))
spark.conf.set('spark.sql.session.timeZone','UTC')
run_id=str(uuid.uuid4())
audit={'run_id':run_id,'landing_run_id':p_landing_run_id,'environment':'fabric','manifest_sha256':p_manifest_sha256,'status':'started','started_at_utc':datetime.now(timezone.utc).isoformat(),'sources':[]}
def compare(a,b):
    a=a.select(*TYPED_FIELDS);b=b.select(*TYPED_FIELDS)
    assert a.schema==b.schema, 'Tipos diferentes da referencia independente'
    assert a.exceptAll(b).limit(1).count()==0 and b.exceptAll(a).limit(1).count()==0,'Diferenca de negocio'
def lineage(df,source):
    return df.withColumn('source_id',F.lit(source['source_id'])).withColumn('source_sha256',F.lit(source['source_sha256'])).withColumn('run_id',F.lit(run_id)).withColumn('ingested_at_utc',F.lit(audit['started_at_utc'])).withColumn('is_synthetic',F.lit(False))
try:
    for source in manifest['sources']:
        source_id=source['source_id'];sha=source['source_sha256']
        assert re.fullmatch(r'anp_20\d{2}_[12]',source_id) and re.fullmatch('[0-9a-f]{64}',sha)
        landing=files/'landing/anp-history'/source_id/p_landing_run_id/source['filename']
        raw_bytes=landing.read_bytes();assert hashlib.sha256(raw_bytes).hexdigest()==sha
        raw_dir=files/'raw/anp-history'/source_id/sha;raw_dir.mkdir(parents=True,exist_ok=True)
        preserved=raw_dir/source['filename']
        if preserved.exists():assert preserved.read_bytes()==raw_bytes
        else:preserved.write_bytes(raw_bytes)
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            members=[x for x in archive.infolist() if not x.is_dir()]
            assert len(members)==1 and members[0].filename.lower().endswith('.csv')
            csv_bytes=archive.read(members[0])
        assert hashlib.sha256(csv_bytes).hexdigest()==source['csv_sha256']
        parsed=csv.reader(io.StringIO(csv_bytes.decode('utf-8-sig')),delimiter=';',strict=True)
        assert next(parsed)==HEADERS
        count=0
        for row in parsed:
            assert len(row)==len(HEADERS)
            count+=1
        assert count==source['counts']['received']
        extracted=files/'extracted/anp-history'/source_id/sha/'source.csv';extracted.parent.mkdir(parents=True,exist_ok=True)
        if extracted.exists():assert extracted.read_bytes()==csv_bytes
        else:extracted.write_bytes(csv_bytes)
        schema=T.StructType([T.StructField(h,T.StringType(),True) for h in HEADERS])
        raw=(spark.read.schema(schema).option('header',True).option('sep',';').option('encoding','UTF-8').option('mode','FAILFAST').option('multiLine',True).option('quote','"').option('escape','"').csv(extracted.relative_to(files.parent).as_posix()).toDF(*RAW_COLUMNS).fillna(''))
        assert raw.count()==count
        bronze=lineage(raw.withColumn('raw_row_sha256',F.sha2(F.to_json(F.struct(*RAW_COLUMNS)),256)),source)
        predicate="source_sha256 = '"+sha+"'"
        bronze.write.format('delta').mode('overwrite').option('replaceWhere',predicate).saveAsTable('hist_bronze_anp')
        persisted=spark.table('hist_bronze_anp').where(predicate)
        assert persisted.count()==count
        parts=classify(persisted,lookup,source['scope'])
        try:
            actual=category_counts(parts)
            expected={'selected':count,'invalid':source['counts']['invalid'],'exact_duplicate_excess':source['counts']['exact_duplicate_excess'],'conflicting_rows_after_exact_dedup':source['counts']['conflicting_rows'],'accepted':source['counts']['accepted']}
            assert actual==expected,(source_id,actual,expected)
            for category,table in [('invalid','hist_quarentena'),('duplicates','hist_duplicatas'),('conflicts','hist_conflitos')]:
                lineage(parts[category],source).write.format('delta').mode('overwrite').option('replaceWhere',predicate).saveAsTable(table)
            accepted=parts['accepted']
            ref=spark.read.parquet('Files/'+p_bundle_relative_path+'/'+source_id+'.parquet').withColumn('preco_venda',F.col('preco_venda').cast('decimal(10,3)'))
            compare(ref,accepted)
            if spark.catalog.tableExists('hist_silver_versoes'):
                previous=spark.table('hist_silver_versoes').where(predicate)
                if previous.limit(1).count():compare(previous,accepted)
            # Escrita por hash nao remove versoes de outros arquivos nem publica Gold.
            lineage(accepted,source).write.format('delta').mode('overwrite').option('replaceWhere',predicate).saveAsTable('hist_silver_versoes')
            compare(ref,spark.table('hist_silver_versoes').where(predicate))
            audit['sources'].append({'source_id':source_id,'source_sha256':sha,'counts':actual,'full_typed_comparison_passed':True})
        finally:
            parts['classified'].unpersist()
    audit['status']='historical_versions_silver_validated'
except Exception as exc:
    audit.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1500])
    raise
finally:
    audit['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    target=files/'audit/history';target.mkdir(parents=True,exist_ok=True)
    (target/(run_id+'.json')).write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(audit),flush=True)
notebookutils.notebook.exit(json.dumps(audit))
