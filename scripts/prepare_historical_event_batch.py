"""Prepara lote finito e manifesto sem abrir transporte ou emitir eventos."""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from fuelwatch.historical_events import generate_historical_events

benchmark=json.loads((root/'evidence/phase2/streaming/benchmark.json').read_text())
run=str(uuid4())
events=generate_historical_events(run,datetime.now(timezone.utc),benchmark)
folder=root/'.local/phase2-streaming'/run
folder.mkdir(parents=True,exist_ok=False)
files={}
for name,rows in [('seed',events[:10]),('baseline',events[10:-1]),('transition',events[-1:]),('reinject',events[:20])]:
    payload=''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows).encode()
    (folder/(name+'.jsonl')).write_bytes(payload)
    files[name+'.jsonl']={'rows':len(rows),'sha256':hashlib.sha256(payload).hexdigest()}
manifest={'status':'prepared_not_emitted','lab_run_id':run,'is_synthetic':True,'source_is_anp':False,
    'benchmark':benchmark,'unique_event_ids':1000,'reinjected_events':20,'late_fixture_events':10,
    'expected_classifications':dict(Counter(e['benchmark_status'] for e in events)),
    'files':files,'prepared_at_utc':datetime.now(timezone.utc).isoformat()}
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
(root/'evidence/phase2/streaming/prepared-batch.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'lab_run_id':run,'status':manifest['status'],'classifications':manifest['expected_classifications']}))
