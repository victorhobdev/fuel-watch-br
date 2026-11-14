"""Exportacao de QA do relatorio real; acompanha o mesmo exportId."""
import json
import time
import zipfile
import argparse

import requests

from client import ROOT, credential
from powerbi import request

c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
folder = ROOT / '.local/phase2-bi'
s = json.loads((folder / 'binding.json').read_text())
base = f"groups/{c['workspace_id']}/reports/{s['report_id']}"
parser = argparse.ArgumentParser()
parser.add_argument('--product', choices=['GASOLINA', 'GNV'], default='GASOLINA')
parser.add_argument('--page', choices=['nacional_panorama', 'nacional_comparacoes'], default='nacional_panorama')
parser.add_argument('--revision', default='v1')
parser.add_argument('--uf', choices=['RJ','SP'])
parser.add_argument('--brand', choices=['BRANCA'])
args = parser.parse_args()
stem = 'report-' + args.page + '-' + args.product.lower() + '-' + args.revision
if args.uf: stem += '-' + args.uf.lower()
if args.brand: stem += '-' + args.brand.lower()
filters = ["Produtos/Combustivel eq '" + args.product + "'"]
if args.uf: filters.append("Estados/UF eq '" + args.uf + "'")
if args.brand: filters.append("Marcas/Bandeira eq '" + args.brand + "'")
saved = folder / (stem + '-accepted.json')
if saved.exists():
    accepted = json.loads(saved.read_text())
else:
    accepted = request('POST', base + '/ExportTo', {'format': 'PDF',
        'powerBIReportConfiguration': {'pages': [{'pageName': args.page}], 'settings': {'locale': 'pt-BR'}, 'reportLevelFilters': [{'filter': ' and '.join(filters)}]}})
    saved.write_text(json.dumps(accepted, indent=2))
deadline = time.monotonic() + 600
while True:
    status = request('GET', base + '/exports/' + accepted['id'])
    (folder / (stem + '-status.json')).write_text(json.dumps(status, indent=2))
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
file = folder / (stem + '.bin')
file.write_bytes(response.content)
if response.content.startswith(b'\x89PNG'):
    file.replace(folder / (stem + '.png'))
elif response.content.startswith(b'%PDF'):
    file.replace(folder / (stem + '.pdf'))
elif zipfile.is_zipfile(file):
    with zipfile.ZipFile(file) as archive:
        for name in archive.namelist():
            if name.lower().endswith('.png'):
                (folder / ('render-' + name.rsplit('/', 1)[-1])).write_bytes(archive.read(name))
print('Real report rendering downloaded for inspection', flush=True)
