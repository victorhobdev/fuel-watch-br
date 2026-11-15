"""Reconcilia as respostas de porte e cobertura com T-SQL real."""
import json
import argparse
from datetime import datetime, timezone
from client import ROOT
from warehouse import connect, results
from evidence import write_json

expected=json.loads((ROOT/'evidence/phase2/context/answers-local.json').read_text(encoding='utf8'))['answers']['population_price_and_coverage']
parser=argparse.ArgumentParser();parser.add_argument('--rebuild',action='store_true');args=parser.parse_args()
with connect() as cn:
    cn.timeout=900
    cur=cn.cursor()
    results(cur.execute((ROOT/'sql/analytics/04_population_prices.sql').read_text(encoding='utf8')))
    query='''WITH base AS (
 SELECT * FROM analise_hist.populacao_municipio
 WHERE ano_referencia=2025 AND produto='GASOLINA' AND moeda='BRL' AND unidade='litro'
 )
 SELECT DISTINCT porte_populacional,
 COUNT_BIG(*) OVER(PARTITION BY porte_populacional) AS municipios,
 SUM(coletas) OVER(PARTITION BY porte_populacional) AS coletas,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY preco_mediano) OVER(PARTITION BY porte_populacional) AS mediana_municipios,
 PERCENTILE_CONT(0.25) WITHIN GROUP(ORDER BY preco_mediano) OVER(PARTITION BY porte_populacional) AS q1_preco,
 PERCENTILE_CONT(0.75) WITHIN GROUP(ORDER BY preco_mediano) OVER(PARTITION BY porte_populacional) AS q3_preco,
 PERCENTILE_CONT(0.5) WITHIN GROUP(ORDER BY postos_pesquisados_por_100mil) OVER(PARTITION BY porte_populacional) AS mediana_postos_por_100mil
 FROM base ORDER BY porte_populacional'''
    actual=results(cur.execute(query))[0]
    assert len(actual)==len(expected)
    for a,b in zip(actual,expected):
        assert a.keys()==b.keys()
        for k in a:
            if k=='porte_populacional': assert a[k]==b[k]
            else: assert abs(float(a[k])-float(b[k]))<0.000001,(k,a,b)
    write_json(ROOT/('evidence/phase2/deployment/rebuild-population-answers.json' if args.rebuild else 'evidence/phase2/context/population-answers-fabric.json'),{
      'status':'population_price_and_coverage_answers_reconciled','environment':'fabric',
      'checked_at_utc':datetime.now(timezone.utc).isoformat(),'query':query,'answers':actual})
    print(json.dumps(actual,default=str,ensure_ascii=False),flush=True)
