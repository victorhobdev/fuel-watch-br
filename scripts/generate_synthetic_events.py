"""Prepara lote finito e manifesto; nao abre conexao ou envia eventos."""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fuelwatch.synthetic_events import generate_events, reinjections

run_id = str(uuid4())
start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=1000)
events = generate_events(run_id, start)
duplicates = reinjections(events)
folder = ROOT / '.local/m10' / run_id
folder.mkdir(parents=True, exist_ok=False)
files = {}
for name, rows in [('seed.jsonl', events[:10]), ('baseline.jsonl', events[10:-1]), ('transition.jsonl', events[-1:]), ('reinject.jsonl', duplicates)]:
    payload = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows).encode()
    (folder / name).write_bytes(payload)
    files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(payload).hexdigest()}
manifest = {'status': 'prepared_not_emitted', 'is_synthetic': True, 'lab_run_id': run_id,
            'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'unique_event_ids': 1000,
            'reinjected_events': 20, 'late_fixture_events': 10, 'stations': 10,
            'controlled_transition': {'posto_id': 'SYNTHETIC_010', 'from': '6.100', 'to': '7.500', 'threshold': '7.000'},
            'files': files, 'source_is_anp': False}
(folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps(manifest), flush=True)
