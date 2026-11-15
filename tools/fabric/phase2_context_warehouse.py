"""Valida visibilidade SQL e preservação das coletas nos joins de contexto."""
import json
import argparse
from datetime import datetime, timezone

from client import ROOT
from evidence import write_json
from warehouse import connect, results

pop = json.loads((ROOT / 'evidence/phase2/context/population-join-local.json').read_text(encoding='utf8'))
weather = json.loads((ROOT / 'evidence/phase2/context/weather-weekly-local.json').read_text(encoding='utf8'))
parser=argparse.ArgumentParser();parser.add_argument('--rebuild',action='store_true');args=parser.parse_args()
with connect() as cn:
    cn.timeout = 900
    cur = cn.cursor()
    before = results(cur.execute('SELECT * FROM gold_hist.publication'))[0]
    for table, key in [('population', 'municipio_ibge,ano_referencia'),
                       ('weather_municipal_weekly', 'municipio_ibge,week_start')]:
        src = 'lh_fuelwatch.dbo.f2_context_' + table
        assert cur.execute('SELECT COUNT_BIG(*) FROM (SELECT ' + key + ',COUNT_BIG(*) AS n FROM ' + src +
                           ' GROUP BY ' + key + ' HAVING COUNT_BIG(*)>1) x').fetchone()[0] == 0, table
    results(cur.execute((ROOT / 'sql/analytics/03_contexto.sql').read_text(encoding='utf8')))
    totals = results(cur.execute('SELECT COUNT_BIG(*) AS rows, SUM(CAST(preco_venda*1000 AS bigint)) AS price_mills, '
        "SUM(CASE WHEN populacao IS NULL THEN 1 ELSE 0 END) AS no_population FROM analise_hist.coletas_contexto"))[0][0]
    assert totals['rows'] == pop['before_rows'] == weather['price_rows_before'], totals
    assert totals['price_mills'] == pop['before_sum_price_mills'] == weather['sum_price_mills_before'], totals
    assert totals['no_population'] == sum(x['coletas_sem_populacao'] for x in pop['by_year']), totals
    states = results(cur.execute('SELECT weather_status,COUNT_BIG(*) AS n FROM analise_hist.coletas_contexto GROUP BY weather_status'))[0]
    assert {x['weather_status']: x['n'] for x in states} == weather['price_rows_by_status'], states
    assert before == results(cur.execute('SELECT * FROM gold_hist.publication'))[0]
    report = {'status': 'context_join_reconciled', 'environment': 'fabric',
        'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'totals': totals,
        'weather_status': states, 'source_publication_unchanged': True,
        'reference_uniqueness_verified': True, 'source_publication': before}
    write_json(ROOT / ('evidence/phase2/deployment/rebuild-context-join.json' if args.rebuild else 'evidence/phase2/context/warehouse-join.json'), report)
    print(json.dumps(report, default=str, ensure_ascii=False), flush=True)
