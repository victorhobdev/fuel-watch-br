"""Gera somente o wrapper; nao altera notebooks e pacotes aceitos M00-M04."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parameters = '''p_root_run_id = "00000000-0000-0000-0000-000000000000"
p_phase = "bronze"
p_fault_stage = "none"
p_scope_id = "anp-2026-1-rj-gasolina"
p_source_sha256 = "a2c95e5dfa324a9d7253d4e8d53022e0c08dcc5eb6f18551527ee9f29305c54c"
'''
body = (ROOT / "notebooks/m05_sources/08_pipeline_stage.py").read_text(encoding="utf-8")
notebook = {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Synapse PySpark", "language": "Python", "name": "synapse_pyspark"},
                         "language_info": {"name": "python"}},
            "cells": [{"cell_type": "code", "execution_count": None, "outputs": [],
                       "metadata": metadata, "source": source.splitlines(keepends=True)}
                      for metadata, source in [({"tags": ["parameters"]}, parameters), ({}, body)]]}
(ROOT / "notebooks/08_pipeline_stage.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("notebooks/08_pipeline_stage.ipynb preparado; execucao Fabric pendente")
