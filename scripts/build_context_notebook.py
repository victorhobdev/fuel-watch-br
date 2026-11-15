"""Gera notebook Fabric que valida e publica referências de contexto imutáveis."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
inputs = {}
for name in ['population', 'weather_municipal_weekly']:
    path = root / 'data/artifacts/context' / (name + '.parquet')
    inputs[name] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

code = '''import hashlib, json, uuid
from pathlib import Path
from datetime import datetime, timezone
from pyspark.sql import functions as F

inputs = INPUTS
files = Path('/lakehouse/default/Files')
started = datetime.now(timezone.utc).isoformat()
run_id = str(uuid.uuid4())
result = {'run_id': run_id, 'environment': 'fabric', 'started_at_utc': started, 'inputs': {}}
for name, spec in inputs.items():
    relative = 'context/' + spec['sha256'] + '/' + name + '.parquet'
    path = files / relative
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual_hash != spec['sha256']:
        raise ValueError('Arquivo de contexto difere do aprovado: ' + name)
    incoming = spark.read.parquet('Files/' + relative)
    keys = ['municipio_ibge', 'ano_referencia'] if name == 'population' else ['municipio_ibge', 'week_start']
    if incoming.groupBy(*keys).count().where('count > 1').limit(1).count():
        raise ValueError('Chave de contexto duplicada: ' + name)
    table = 'f2_context_' + name
    if spark.catalog.tableExists(table):
        existing = spark.table(table)
        if incoming.schema != existing.schema or incoming.exceptAll(existing).limit(1).count() or existing.exceptAll(incoming).limit(1).count():
            raise ValueError('Tabela existente difere do snapshot: ' + table)
        action = 'reused'
    else:
        incoming.write.format('delta').mode('errorifexists').saveAsTable(table)
        action = 'created'
    stored = spark.table(table)
    if incoming.exceptAll(stored).limit(1).count() or stored.exceptAll(incoming).limit(1).count():
        raise ValueError('Tabela publicada difere do arquivo: ' + table)
    result['inputs'][name] = {'sha256': actual_hash, 'rows': stored.count(), 'table': table, 'action': action}
result['status'] = 'context_reference_tables_validated'
result['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
audit = files / 'audit' / 'phase2_context' / run_id
audit.mkdir(parents=True, exist_ok=False)
(audit / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))
mssparkutils.notebook.exit(json.dumps(result, ensure_ascii=False))
'''.replace('INPUTS', repr(inputs))
notebook = {'nbformat': 4, 'nbformat_minor': 5,
    'metadata': {'kernelspec': {'name': 'synapse_pyspark', 'display_name': 'Synapse PySpark', 'language': 'Python'},
                 'language_info': {'name': 'python'}},
    'cells': [{'cell_type': 'markdown', 'metadata': {}, 'source': ['# Fase 2 — referências de população e clima\n',
        'Verifica hashes, unicidade e igualdade integral antes de disponibilizar tabelas Delta.']},
        {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': code.splitlines(keepends=True)}]}
out = root / 'notebooks/15_context_references.ipynb'
out.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
print(json.dumps(inputs))
