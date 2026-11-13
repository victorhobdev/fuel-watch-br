"""Experimento somente leitura. Nao publica ou altera tabelas oficiais."""
import hashlib
import json
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import functions as F

experiment_id = str(uuid.uuid4())
folder = Path('/lakehouse/default/Files/audit/m09') / experiment_id
folder.mkdir(parents=True, exist_ok=False)
audit = {'experiment_id': experiment_id, 'protocol': 'weekly_shuffle_200_vs_8_v1',
         'status': 'started', 'environment': 'fabric', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
         'spark_version': spark.version, 'python_version': sys.version.split()[0],
         'application_id': spark.sparkContext.applicationId,
         'source_delta_version': 0, 'samples': [], 'warmups': [], 'cu_or_cost_measured': False}
shuffle_key = 'spark.sql.shuffle.partitions'
previous_shuffle = spark.conf.get(shuffle_key)
audit['original_shuffle_partitions'] = previous_shuffle
audit['aqe_enabled'] = spark.conf.get('spark.sql.adaptive.enabled')
audit['aqe_coalesce_enabled'] = spark.conf.get('spark.sql.adaptive.coalescePartitions.enabled')
source = None


def persist():
    (folder / 'summary.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')


def normalized(rows):
    return sorted([[None if v is None else str(v) for v in row] for row in rows])


def weekly():
    frame = source.withColumn('inicio_semana_iso', F.to_date(F.date_trunc('week', F.col('data_coleta'))))
    grouped = frame.groupBy('inicio_semana_iso', 'municipio_ibge', 'produto', 'moeda', 'unidade').agg(
        F.count('*').alias('coletas'), F.countDistinct('cnpj').alias('postos_observados'),
        F.sum('preco_venda').alias('soma_precos'), F.min('preco_venda').alias('preco_minimo'),
        F.max('preco_venda').alias('preco_maximo'),
        F.sum(F.col('preco_incomum_iqr').cast('long')).alias('precos_incomuns'))
    return grouped.withColumn('ano_iso', F.year(F.date_add('inicio_semana_iso', 3))).withColumn(
        'semana_iso', F.weekofyear('inicio_semana_iso')).select(
        'inicio_semana_iso', 'ano_iso', 'semana_iso', 'municipio_ibge', 'produto', 'moeda', 'unidade',
        'coletas', 'postos_observados', 'soma_precos', 'preco_minimo', 'preco_maximo', 'precos_incomuns')


try:
    current_before = spark.sql('DESCRIBE HISTORY silver_preco_publicado').agg(F.max('version')).first()[0]
    source = spark.sql('SELECT * FROM silver_preco_publicado VERSION AS OF 0').where(
        F.col('scope_id') == 'anp-2026-1-rj-gasolina')
    provenance = source.select('snapshot_id', 'source_sha256', 'ibge_sha256', 'is_synthetic').distinct().collect()
    expected = ('3da66482-2dad-489f-8450-b7ded2005f3d',
                'a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c',
                '2338ca0e4f482e065e14d1aec04d69ba525ba69ec4cc103161f6cb178163dad0', False)
    assert len(provenance) == 1 and tuple(provenance[0]) == expected, 'Snapshot/proveniencia divergente'
    assert str(source.schema['preco_venda'].dataType) == 'DecimalType(10,3)'
    assert str(source.schema['data_coleta'].dataType) == 'DateType()'
    files = source.inputFiles()
    hadoop = spark.sparkContext._jsc.hadoopConfiguration()
    bytes_total = 0
    for name in files:
        path = spark._jvm.org.apache.hadoop.fs.Path(name)
        bytes_total += path.getFileSystem(hadoop).getFileStatus(path).getLen()
    audit.update({'snapshot_id': expected[0], 'source_sha256': expected[1], 'ibge_sha256': expected[2],
                  'input_files': len(files), 'input_file_bytes': bytes_total, 'schema': source.schema.jsonValue(),
                  'current_delta_version_before': current_before})
    source = source.cache()
    load_start = time.perf_counter()
    count = source.count()
    audit['cache_materialization_seconds'] = time.perf_counter() - load_start
    counts = (count, source.select('cnpj').distinct().count(), source.select('municipio_ibge').distinct().count())
    assert counts == (8052, 502, 27), counts
    audit['input_rows'], audit['stations'], audit['municipalities'] = counts
    expected_rows = None
    for phase, partitions in [('baseline', 200), ('intervention', 8)]:
        spark.conf.set(shuffle_key, partitions)
        for index in range(4):
            group = experiment_id + '-' + phase + '-' + str(index)
            spark.sparkContext.setJobGroup(group, group, interruptOnCancel=True)
            frame = weekly()
            start = time.perf_counter()
            rows = frame.collect()
            seconds = time.perf_counter() - start
            canonical = normalized(rows)
            assert len(canonical) == 656
            if expected_rows is None:
                expected_rows = canonical
                (folder / 'weekly-business.json').write_text(json.dumps(canonical), encoding='utf-8')
            assert canonical == expected_rows, 'Agregacao mudou entre medicoes'
            plan = frame._jdf.queryExecution().executedPlan().toString()
            plan_name = phase + '-' + str(index) + '-plan.txt'
            (folder / plan_name).write_text(plan, encoding='utf-8')
            tracker = spark.sparkContext.statusTracker()
            jobs = list(tracker.getJobIdsForGroup(group))
            stages = set()
            for job in jobs:
                info = tracker.getJobInfo(job)
                if info:
                    stages.update(int(stage) for stage in info.stageIds)
            tasks = sum(tracker.getStageInfo(stage).numTasks for stage in stages if tracker.getStageInfo(stage))
            sample = {'phase': phase, 'iteration': index, 'shuffle_partitions': partitions, 'seconds': seconds,
                      'groups': len(rows), 'business_sha256': hashlib.sha256(json.dumps(canonical).encode()).hexdigest(),
                      'plan_file': plan_name, 'plan_sha256': hashlib.sha256(plan.encode()).hexdigest(),
                      'job_ids': [int(job) for job in jobs], 'stage_ids': sorted(stages), 'stage_tasks': int(tasks)}
            audit['warmups' if index == 0 else 'samples'].append(sample)
            persist()
            print(json.dumps(sample), flush=True)
    audit['medians_seconds'] = {phase: statistics.median(s['seconds'] for s in audit['samples'] if s['phase'] == phase)
                               for phase in ['baseline', 'intervention']}
    current_after = spark.sql('DESCRIBE HISTORY silver_preco_publicado').agg(F.max('version')).first()[0]
    assert current_before == current_after, 'Silver alterada durante experimento'
    audit.update({'status': 'benchmark_measured', 'current_delta_version_after': current_after,
                  'source_version_unchanged': True, 'official_tables_written': False,
                  'gold_reconciliation': 'pending_external_sql_comparison', 'production_configuration_changed': False})
except Exception as exc:
    audit.update({'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)})
    raise
finally:
    spark.conf.set(shuffle_key, previous_shuffle)
    audit['shuffle_restored'] = spark.conf.get(shuffle_key) == previous_shuffle
    if source is not None:
        source.unpersist(blocking=True)
    spark.sparkContext.setLocalProperty('spark.jobGroup.id', None)
    audit['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    persist()
print(json.dumps(audit), flush=True)
