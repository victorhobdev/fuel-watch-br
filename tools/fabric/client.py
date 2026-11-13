"""REST Fabric com o cache Azure isolado. Nao repete escritas em falhas de rede."""
import os
import time
from pathlib import Path
from urllib.parse import urlparse
import json

import requests
from azure.identity import AzureCliCredential

ROOT = Path(__file__).resolve().parents[2]
identity = os.environ.get("FUELWATCH_IDENTITY", "author")
if identity not in {"author", "reader"}:
    raise ValueError("FUELWATCH_IDENTITY deve ser author ou reader")
os.environ["AZURE_CONFIG_DIR"] = str(ROOT / (".local/azure-reader" if identity == "reader" else ".local/azure"))
credential = AzureCliCredential()
_fabric_token = None


def environment_config():
    path = Path(os.environ.get('FUELWATCH_ENV_FILE', ROOT / '.local/fabric-environment.json')).resolve()
    if not path.is_relative_to((ROOT / '.local').resolve()):
        raise ValueError('Bindings de ambiente devem ficar em .local dentro do projeto')
    return json.loads(path.read_text())


def request(method, path, body=None):
    global _fabric_token
    url = path if path.startswith("https://") else "https://api.fabric.microsoft.com/v1/" + path.lstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname == "api.fabric.microsoft.com" or parsed.hostname.endswith(".analysis.windows.net")):
        raise ValueError("Endpoint Fabric nao permitido")
    if _fabric_token is None or _fabric_token.expires_on <= time.time() + 120:
        _fabric_token = credential.get_token("https://api.fabric.microsoft.com/.default")
    token = _fabric_token.token
    read_only = method.upper() == "GET" or (method.upper() == "POST" and parsed.path.endswith("/queryactivityruns"))
    for attempt in range(3 if read_only else 1):
        try:
            response = requests.request(method, url, json=body,
                                        headers={"Authorization": "Bearer " + token}, timeout=60)
            break
        except (requests.ConnectionError, requests.Timeout):
            if not read_only or attempt == 2:
                raise
            time.sleep(2 ** attempt)
    response.raise_for_status()
    return response


def definition_operation(path, body=None):
    response = request("POST", path, body)
    if response.status_code == 202:
        location = response.headers["Location"]
        (ROOT / ".local/fabric-last-definition-operation.json").write_text(json.dumps({"location": location}))
        while True:
            time.sleep(min(int(response.headers.get("Retry-After", "2")), 60))
            response = request("GET", location)
            state = response.json()
            print("definition operation:", state.get("status"), flush=True)
            if state.get("status") == "Failed":
                raise RuntimeError(state.get("error"))
            if state.get("status") == "Succeeded":
                if path.split('?')[0].endswith('/updateDefinition'):
                    return {}
                response = request("GET", location.rstrip("/") + "/result")
                break
    return response.json() if response.content else {}
