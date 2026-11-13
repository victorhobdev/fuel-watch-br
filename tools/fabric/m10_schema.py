"""Cria o schema isolado e confirma que ainda nao ha eventos."""
import json

from client import ROOT
from kusto import execute, rows

folder = ROOT / '.local/m10-api'
for index, command in enumerate((ROOT / 'kql/schema.kql').read_text().splitlines()):
    if not command or command.startswith('//'):
        continue
    result = execute(command, management=True)
    (folder / ('schema-' + str(index) + '.json')).write_text(json.dumps(result, indent=2))
    print('KQL schema command accepted:', index, flush=True)
result = rows(execute('lab_preco_eventos | count'))
assert result == [{'Count': 0}], 'Ja ha eventos; inspecionar antes de emitir'
print('KQL table validated empty; no events emitted', flush=True)
