"""Data-plane Kusto restrito ao endpoint do laboratorio em .local."""
import json
from urllib.parse import urlparse

import requests

from client import ROOT, credential


def execute(csl, management=False, parameters=None):
    item = json.loads((ROOT / '.local/m10-api/database-item.json').read_text())
    endpoint = item['properties']['queryServiceUri']
    url = urlparse(endpoint)
    assert url.scheme == 'https' and url.hostname.endswith('.kusto.fabric.microsoft.com')
    token = credential.get_token('https://kusto.kusto.windows.net/.default').token
    body = {'db': item['id'], 'csl': csl}
    if parameters:
        body['properties'] = json.dumps({'Parameters': parameters})
    response = requests.post(endpoint.rstrip('/') + ('/v1/rest/mgmt' if management else '/v1/rest/query'),
        json=body, headers={'Authorization': 'Bearer ' + token}, timeout=120)
    if not response.ok:
        (ROOT / '.local/m10-api/last-kusto-error.json').write_text(response.text)
    response.raise_for_status()
    payload = response.json()
    assert 'error' not in payload, 'Erro Kusto: inspecionar retorno privado'
    return payload


def rows(payload):
    tables = payload['Tables']
    toc = next(t for t in tables if [c['ColumnName'] for c in t['Columns']] == ['Ordinal', 'Kind', 'Name', 'Id', 'PrettyName'])
    results = [row[0] for row in toc['Rows'] if row[1:3] == ['QueryResult', 'PrimaryResult']]
    statuses = [row[0] for row in toc['Rows'] if row[1] == 'QueryStatus']
    assert len(results) == 1 and len(statuses) == 1, 'Resultado/status Kusto ambiguo ou ausente'
    status = tables[statuses[0]]
    fields = [c['ColumnName'] for c in status['Columns']]
    for values in status['Rows']:
        row = dict(zip(fields, values))
        if row['StatusCode'] != 0 or row['Severity'] <= 2:
            raise RuntimeError('Kusto reportou falha/resultado parcial; nao aceitar como consulta valida')
    table = tables[results[0]]
    columns = [c['ColumnName'] for c in table['Columns']]
    return [dict(zip(columns, row)) for row in table['Rows']]
