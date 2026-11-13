"""REST Fabric com o cache Azure isolado. Nao repete escritas em falhas de rede."""
import os
import time
from pathlib import Path
from urllib.parse import urlparse
import json

import requests
from azure.identity import AzureCliCredential

ROOT = Path(__file__).resolve().parents[2]
os.environ["AZURE_CONFIG_DIR"] = str(ROOT / ".local/azure")
credential = AzureCliCredential()


def request(method, path, body=None):
    url = path if path.startswith("https://") else "https://api.fabric.microsoft.com/v1/" + path.lstrip("/")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname == "api.fabric.microsoft.com" or parsed.hostname.endswith(".analysis.windows.net")):
        raise ValueError("Endpoint Fabric nao permitido")
    token = credential.get_token("https://api.fabric.microsoft.com/.default").token
    response = requests.request(method, url, json=body,
                                headers={"Authorization": "Bearer " + token}, timeout=60)
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
                response = request("GET", location.rstrip("/") + "/result")
                break
    return response.json() if response.content else {}
