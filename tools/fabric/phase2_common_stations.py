"""Instala a view histórica e reconcilia integralmente com a referência local."""
import hashlib
import json
import sys
import argparse
from datetime import datetime, timezone

from client import ROOT
from warehouse import connect, results

sys.path.insert(0, str(ROOT))
from fuelwatch.analytics import row_hash

expected = json.loads((ROOT / 'data/artifacts/analytics-history/common-stations/reference.json').read_text())
parser=argparse.ArgumentParser();parser.add_argument('--rebuild',action='store_true');args=parser.parse_args()
sql = (ROOT / 'sql/analytics/02_postos_comuns.sql').read_text(encoding='utf8')
with connect() as cn:
    cn.timeout = 900
    cur = cn.cursor()
    before = results(cur.execute('SELECT * FROM gold_hist.publication'))[0]
    results(cur.execute(sql))
    cur.execute('SELECT ' + ','.join('[' + c + ']' for c in expected['columns']) +
                ' FROM analise_hist.postos_comuns_semestre')
    hashes = []
    while batch := cur.fetchmany(10000):
        hashes.extend(row_hash(row, expected['kinds']) for row in batch)
    fingerprint = hashlib.sha256('\n'.join(sorted(hashes)).encode()).hexdigest()
    assert len(hashes) == expected['rows'] and fingerprint == expected['business_sha256'], (len(hashes), fingerprint)
    assert before == results(cur.execute('SELECT * FROM gold_hist.publication'))[0]
    record = {'status': 'common_stations_full_comparison_passed', 'environment': 'fabric',
              'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'rows': len(hashes),
              'business_sha256': fingerprint, 'by_period': expected['by_period'],
              'publication_unchanged': True, 'source_publication': before}
    out = ROOT / ('evidence/phase2/deployment/rebuild-common-stations.json' if args.rebuild else 'evidence/phase2/analytics-history/common-stations.json')
    out.write_text(json.dumps(record, indent=2, default=str) + '\n', encoding='utf8')
    print(json.dumps(record, default=str), flush=True)
