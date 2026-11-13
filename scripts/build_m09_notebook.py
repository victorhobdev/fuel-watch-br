"""Gera notebook de medicao sem bindings privados."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'notebooks/m09_sources/09_weekly_benchmark.py').read_text(encoding='utf-8')
compile(source, '09_weekly_benchmark.py', 'exec')
notebook = {'nbformat': 4, 'nbformat_minor': 5,
            'metadata': {'kernelspec': {'display_name': 'Synapse PySpark', 'language': 'Python', 'name': 'synapse_pyspark'},
                         'language_info': {'name': 'python'}},
            'cells': [{'cell_type': 'code', 'execution_count': None, 'outputs': [], 'metadata': {},
                       'source': source.splitlines(keepends=True)}]}
(ROOT / 'notebooks/09_weekly_benchmark.ipynb').write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('Notebook 09 gerado; nenhum job Fabric iniciado')
