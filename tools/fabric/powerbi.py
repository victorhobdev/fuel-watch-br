"""API Power BI com a mesma identidade delegada, sem tokens persistidos."""
import requests
from client import ROOT, credential


def request(method, path, body=None):
    assert not path.startswith(('http:', 'https:'))
    token = credential.get_token('https://analysis.windows.net/powerbi/api/.default').token
    response = requests.request(method, 'https://api.powerbi.com/v1.0/myorg/' + path.lstrip('/'),
        headers={'Authorization': 'Bearer ' + token}, json=body, timeout=120)
    if not response.ok:
        folder = ROOT / '.local/m11-api'
        folder.mkdir(exist_ok=True)
        (folder / 'powerbi-error.private.json').write_text(response.text)
        print('Power BI response:', response.status_code, 'details saved privately', flush=True)
    response.raise_for_status()
    return response.json() if response.content else {}
