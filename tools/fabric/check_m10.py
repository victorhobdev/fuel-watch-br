"""Compara conjuntos/payloads reais, quatro consultas KQL e acao Activator."""
import json
from datetime import datetime, timezone
from decimal import Decimal

from client import ROOT
from kusto import execute, rows

run = 'daf2320c-b0bc-4eef-b908-a2dd80939088'
source = ROOT / '.local/m10' / run
expected = [json.loads(line) for name in ['seed', 'baseline', 'transition']
            for line in (source / (name + '.jsonl')).read_text().splitlines()]
queries = (ROOT / 'kql/fuelwatch_lab.kql').read_text().split('declare query_parameters(p_run_id:string);')[1:]
results = []
out = ROOT / 'evidence/fabric/streaming' / run
out.mkdir(parents=True, exist_ok=True)
for index, query in enumerate(queries, 1):
    # Comentarios da consulta seguinte sao inofensivos; cada declaracao e isolada.
    payload = execute('declare query_parameters(p_run_id:string);' + query, parameters={'p_run_id': run})
    actual = rows(payload)
    results.append(actual)
    (out / ('q' + str(index) + '.json')).write_text(json.dumps(actual, indent=2) + '\n')
assert len(results) == 4
latest, windows, received, duplicate_late = results
assert len(latest) == 10 and len(received) == 1000
lookup = {row['event_id']: row for row in expected}
assert set(lookup) == {row['event_id'] for row in received}
for row in received:
    reference = lookup[row['event_id']]
    for key in reference:
        if key == 'event_time':
            assert datetime.fromisoformat(row[key].replace('Z', '+00:00')) == datetime.fromisoformat(reference[key].replace('Z', '+00:00'))
        elif key == 'preco':
            assert Decimal(str(row[key])) == Decimal(reference[key])
        else:
            assert row[key] == reference[key], key
assert next(r for r in latest if r['posto_id'] == 'SYNTHETIC_010')['preco'] == 7.5
assert sum(r['coletas'] for r in windows) == 1000
assert abs(sum(r['soma_precos'] for r in windows) - sum(float(r['preco']) for r in expected)) < 1e-7
assert sum(r['ocorrencias'] - 1 for r in duplicate_late) == 20
assert sum(r['late_fixture'] for r in duplicate_late) == 10
activations = json.loads((ROOT / '.local/m10-api/activations.json').read_text())['structured_content']
assert activations['totalCount'] >= 1
audit = json.loads((ROOT / '.local/m10-api/alert-sql.json').read_text())[0]
jobs = json.loads((ROOT / '.local/m10-api/alert-jobs.json').read_text())['value']
assert len(audit) == 1 and audit[0]['lab_run_id'] == run and audit[0]['is_synthetic']
assert any(j['id'] == audit[0]['pipeline_run_id'] and j['status'] == 'Completed' for j in jobs)
public_activation = [{'activationTime': a['activationTime'], 'ruleId': a['properties']['System.RuleId'],
                      'actionType': a['properties']['System.ActionType']} for a in activations['activations']]
report = {'status': 'data_and_activation_verified_shutdown_pending', 'environment': 'fabric', 'lab_run_id': run,
          'received_unique_ids': 1000, 'full_payload_comparison': True, 'reinjection_excess': 20,
          'late_fixture_events': 10, 'queries_verified': 4, 'activations': public_activation,
          'alert_pipeline_run_id': audit[0]['pipeline_run_id'], 'alert_sql_row_verified': True,
          'external_notifications_sent': False, 'source_is_anp': False,
          'transport_exactly_once_claimed': False, 'checked_at_utc': datetime.now(timezone.utc).isoformat()}
(out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
(out / 'emission.json').write_text((source / 'emission.json').read_text())
(out / 'manifest.json').write_text((source / 'manifest.json').read_text())
print(json.dumps(report), flush=True)
