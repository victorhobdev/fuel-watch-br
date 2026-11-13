"""Exportacao de QA do relatorio real; acompanha o mesmo exportId."""
import json
import time
import zipfile

import requests

from client import ROOT, credential
from powerbi import request

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/m11-api'
s = json.loads((folder / 'binding.json').read_text())
base = f"groups/{c['workspace_id']}/reports/{s['report_id']}"
saved = folder / 'export-accepted-ptbr-v2.json'
if saved.exists():
    accepted = json.loads(saved.read_text())
else:
    accepted = request('POST', base + '/ExportTo', {'format': 'PDF',
        'powerBIReportConfiguration': {'pages': [{'pageName': 'fuelwatch_overview'}], 'settings': {'locale': 'pt-BR'}}})
    saved.write_text(json.dumps(accepted, indent=2))
deadline = time.monotonic() + 600
while True:
    status = request('GET', base + '/exports/' + accepted['id'])
    (folder / 'export-status.json').write_text(json.dumps(status, indent=2))
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
    file.rename(folder / 'report-render-ptbr-v2.pdf')
elif zipfile.is_zipfile(file):
    with zipfile.ZipFile(file) as archive:
        for name in archive.namelist():
            if name.lower().endswith('.png'):
                (folder / ('render-' + name.rsplit('/', 1)[-1])).write_bytes(archive.read(name))
print('Real report rendering downloaded for inspection', flush=True)
