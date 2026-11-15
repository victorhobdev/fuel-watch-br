"""Exportacao de QA do relatorio real; acompanha o mesmo exportId."""
import json
import hashlib
import time
import zipfile
import sys
from datetime import datetime,timezone

import requests

from client import ROOT, credential,environment_config
from powerbi import request

rebuild='--rebuild' in sys.argv
attempt = sys.argv[sys.argv.index('--attempt') + 1] if '--attempt' in sys.argv else None
c = environment_config()
folder = ROOT / ('.local/phase2-rebuild/bi-history' if rebuild else '.local/m11-api')
s = json.loads((folder / 'binding.json').read_text())
base = f"groups/{c['workspace_id']}/reports/{s['report_id']}"
saved = folder / (f'export-{attempt}-accepted.json' if rebuild and attempt else 'export-all-accepted.json' if rebuild else 'export-accepted-ptbr-v2.json')
status_file = folder / (f'export-{attempt}-status.json' if rebuild and attempt else 'export-status.json')
if saved.exists():
    accepted = json.loads(saved.read_text())
else:
    config={'settings': {'locale': 'pt-BR'}}
    if not rebuild:config['pages']=[{'pageName':'fuelwatch_overview'}]
    accepted = request('POST', base + '/ExportTo', {'format': 'PDF','powerBIReportConfiguration':config})
    saved.write_text(json.dumps(accepted, indent=2))
deadline = time.monotonic() + 600
while True:
    status = request('GET', base + '/exports/' + accepted['id'])
    status_file.write_text(json.dumps(status, indent=2))
    print('Report export:', status['status'], flush=True)
    if status['status'] == 'Succeeded':
        break
    assert status['status'] != 'Failed', status
    assert time.monotonic() < deadline, 'Retomar exportId existente'
    time.sleep(15)
token = credential.get_token('https://analysis.windows.net/powerbi/api/.default').token
response = requests.get('https://api.powerbi.com/v1.0/myorg/' + base + '/exports/' + accepted['id'] + '/file',
    headers={'Authorization': 'Bearer ' + token}, timeout=120)
response.raise_for_status()
file = folder / 'report-render-ptbr-v2.bin'
file.write_bytes(response.content)
if response.content.startswith(b'\x89PNG'):
    file.rename(folder / 'report-render-ptbr-v2.png')
elif response.content.startswith(b'%PDF'):
    if rebuild:
        output=ROOT/('evidence/phase2/deployment/rebuild-history-report-'+attempt+'.pdf' if attempt else 'evidence/phase2/deployment/rebuild-history-report.pdf')
        output.write_bytes(response.content)
        record={'status':'report_export_downloaded','environment':'fabric_rebuild','workspace_id':c['workspace_id'],'report_id':s['report_id'],'export_id':accepted['id'],'sha256':hashlib.sha256(response.content).hexdigest(),'bytes':len(response.content),'pdf_path':str(output),'checked_at_utc':datetime.now(timezone.utc).isoformat()}
        record_path=ROOT/('evidence/phase2/deployment/rebuild-history-report-'+attempt+'.json' if attempt else 'evidence/phase2/deployment/rebuild-history-report.json')
        record_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        file.unlink()
        print(json.dumps(record,ensure_ascii=False),flush=True)
    else:file.rename(folder / 'report-render-ptbr-v2.pdf')
elif zipfile.is_zipfile(file):
    with zipfile.ZipFile(file) as archive:
        for name in archive.namelist():
            if name.lower().endswith('.png'):
                (folder / ('render-' + name.rsplit('/', 1)[-1])).write_bytes(archive.read(name))
print('Real report rendering downloaded for inspection', flush=True)
