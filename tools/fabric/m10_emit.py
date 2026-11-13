"""Emissor finito: cada fase exige ledger novo; nenhum retry de envio automatico."""
import argparse
import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

from azure.eventhub import EventData, EventHubProducerClient, TransportType

from client import ROOT, request

parser = argparse.ArgumentParser()
parser.add_argument('manifest', type=Path)
parser.add_argument('--phase', choices=['seed', 'baseline', 'transition', 'reinject'], required=True)
parser.add_argument('--retry-local-import', action='store_true', help='Somente seed rejeitado localmente por dependencia ausente')
args = parser.parse_args()
manifest_path = args.manifest.resolve()
assert manifest_path.is_relative_to((ROOT / '.local/m10').resolve())
manifest = json.loads(manifest_path.read_text())
assert manifest['is_synthetic'] and manifest['source_is_anp'] is False
folder = manifest_path.parent
ledger_file = folder / 'emission.json'
ledger = json.loads(ledger_file.read_text()) if ledger_file.exists() else {'lab_run_id': manifest['lab_run_id'], 'phases': {}}
assert ledger['lab_run_id'] == manifest['lab_run_id']
if args.phase in ledger['phases']:
    prior = ledger['phases'][args.phase]
    assert args.retry_local_import and args.phase == 'seed' and prior.get('error_type') == 'ImportError'
    from kusto import execute, rows
    current = rows(execute('declare query_parameters(p_run_id:string); lab_preco_eventos '
        '| where lab_run_id == p_run_id | count', parameters={'p_run_id': manifest['lab_run_id']}))
    assert current == [{'Count': 0}], 'Ja ha eventos: inspecionar antes de repetir'
    ledger.setdefault('prior_attempts', []).append({'phase': args.phase, **prior})
    del ledger['phases'][args.phase]
order = ['seed', 'baseline', 'transition', 'reinject']
for phase in order[:order.index(args.phase)]:
    assert ledger['phases'].get(phase, {}).get('status') == 'acknowledged', 'Fase anterior nao confirmada'
if args.phase in {'baseline', 'transition'}:
    ready = json.loads((ROOT / '.local/m10-api/activator-ready.json').read_text())
    assert ready['rule_enabled_readback'] and ready['lab_run_id'] == manifest['lab_run_id']
config = json.loads((ROOT / '.local/fabric-environment.json').read_text())
bindings = json.loads((ROOT / '.local/m10-api/binding.json').read_text())
topology = request('GET', f"workspaces/{config['workspace_id']}/eventstreams/{bindings['eventstream']['id']}/topology").json()
assert all(node['status'] == 'Running' for node in topology['sources'] + topology['destinations'])
payload = (folder / (args.phase + '.jsonl')).read_bytes()
assert hashlib.sha256(payload).hexdigest() == manifest['files'][args.phase + '.jsonl']['sha256']
records = [json.loads(line) for line in payload.splitlines()]
assert len(records) == manifest['files'][args.phase + '.jsonl']['rows']
assert all(r['lab_run_id'] == manifest['lab_run_id'] and r['is_synthetic'] for r in records)
connection = json.loads((ROOT / '.local/m10-api/source-connection.private.json').read_text())
client = EventHubProducerClient.from_connection_string(connection['accessKeys']['primaryConnectionString'],
    eventhub_name=connection['eventHubName'], transport_type=TransportType.AmqpOverWebsocket,
    retry_total=0, logging_enable=False)
attempt = {'status': 'sending', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
           'rows': len(records), 'payload_sha256': hashlib.sha256(payload).hexdigest(),
           'sdk_retry_total': 0, 'ingestion_verified': False}
ledger['phases'][args.phase] = attempt
ledger_file.write_text(json.dumps(ledger, indent=2))
try:
    with client:
        batch = client.create_batch(partition_key=manifest['lab_run_id'])
        for row in records:
            event = EventData(json.dumps(row, separators=(',', ':')))
            event.content_type = 'application/json'
            batch.add(event)
        client.send_batch(batch, timeout=60)
    attempt.update({'status': 'acknowledged', 'finished_at_utc': datetime.now(timezone.utc).isoformat()})
except Exception as exc:
    (folder / ('transport-error-' + args.phase + '.private.txt')).write_text(traceback.format_exc())
    attempt.update({'status': 'unconfirmed', 'error_type': type(exc).__name__,
                    'finished_at_utc': datetime.now(timezone.utc).isoformat()})
    # Nao imprimir excecao de transporte: pode conter detalhes da conexao.
    raise SystemExit('Envio sem confirmacao: inspecionar IDs no KQL antes de qualquer nova tentativa')
finally:
    ledger_file.write_text(json.dumps(ledger, indent=2))
print(json.dumps({'lab_run_id': manifest['lab_run_id'], 'phase': args.phase, **attempt}), flush=True)
