"""Respostas locais exploratórias; cada município ou município-semana pesa uma vez."""
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

root = Path(__file__).resolve().parents[1]
con = duckdb.connect()
population = (root / 'data/artifacts/context/municipal_population.parquet').as_posix()
municipal = (root / 'data/artifacts/analytics-history/municipio_semana.parquet').as_posix()
weather = (root / 'data/artifacts/context/weather_municipal_weekly.parquet').as_posix()
queries = {
    'population_price_and_coverage': f"""
      SELECT porte_populacional, COUNT(*) AS municipios, SUM(coletas) AS coletas,
             MEDIAN(preco_mediano) AS mediana_municipios,
             QUANTILE_CONT(preco_mediano,0.25) AS q1_preco,
             QUANTILE_CONT(preco_mediano,0.75) AS q3_preco,
             MEDIAN(postos_pesquisados_por_100mil) AS mediana_postos_por_100mil
      FROM read_parquet('{population}')
      WHERE ano_referencia=2025 AND produto='GASOLINA' AND moeda='BRL' AND unidade='litro'
      GROUP BY porte_populacional ORDER BY porte_populacional""",
    'weather_rain_and_temperature': f"""
      SELECT m.uf, YEAR(m.inicio_semana_iso) AS ano, QUARTER(m.inicio_semana_iso) AS trimestre,
             CASE WHEN w.observed_rain_mm < 10 THEN 'abaixo_10mm'
                  WHEN w.observed_rain_mm < 40 THEN '10_a_40mm' ELSE '40mm_ou_mais' END AS chuva,
             COUNT(*) AS municipios_semanas, COUNT(DISTINCT m.municipio_ibge) AS municipios,
             MEDIAN(m.mediana_municipio) AS mediana_precos,
             QUANTILE_CONT(m.mediana_municipio,0.25) AS q1_precos,
             QUANTILE_CONT(m.mediana_municipio,0.75) AS q3_precos,
             MEDIAN(w.mean_temperature_degC) AS mediana_temperatura
      FROM read_parquet('{municipal}') m JOIN read_parquet('{weather}') w
       ON m.municipio_ibge=w.municipio_ibge AND m.inicio_semana_iso=w.week_start
      WHERE m.produto='GASOLINA' AND m.moeda='BRL' AND m.unidade='litro' AND m.benchmark_elegivel
       AND w.rain_eligible AND w.temperature_eligible AND NOT w.partial_boundary_week
       AND m.uf IN ('RJ','SP') AND YEAR(m.inicio_semana_iso)=2025
      GROUP BY ALL ORDER BY m.uf, ano, trimestre, chuva"""
}
answers = {}
for name, query in queries.items():
    result = con.execute(query)
    columns = [x[0] for x in result.description]
    answers[name] = [dict(zip(columns, row)) for row in result.fetchall()]
    assert answers[name], name + ': amostra vazia'
record = {'status': 'context_exploration_prepared_locally', 'fabric_executed': False,
    'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'answers': answers,
    'interpretation': 'Descritivo; município ou município-semana têm peso igual. Valores nominais, sem causalidade. Chuva é soma das horas válidas sem imputação. Análise de clima estratificada por UF e trimestre.',
    'queries': queries}
out = root / 'evidence/phase2/context/answers-local.json'
out.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf8')
print(json.dumps({name: len(rows) for name, rows in answers.items()}))
