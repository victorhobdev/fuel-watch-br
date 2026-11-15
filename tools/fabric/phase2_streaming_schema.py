"""Prepara tabela isolada e confirma ausência de emissões do novo lote."""
import json
from datetime import datetime,timezone
from client import ROOT
from kusto import execute,rows
from evidence import write_json

manifest=json.loads((ROOT/'evidence/phase2/streaming/prepared-batch.json').read_text())
for statement in (ROOT/'kql/phase2_schema.kql').read_text().splitlines():
 if statement.strip() and not statement.startswith('//'):
  execute(statement,management=True)
observed=rows(execute('declare query_parameters(p_run:string); lab_historical_events | where lab_run_id==p_run | count',parameters={'p_run':manifest['lab_run_id']}))
assert observed==[{'Count':0}],observed
write_json(ROOT/'evidence/phase2/streaming/schema.json',{'status':'isolated_kql_schema_prepared_no_events','environment':'fabric','lab_run_id':manifest['lab_run_id'],'run_rows':0,'checked_at_utc':datetime.now(timezone.utc).isoformat()})
print('Schema KQL isolado preparado; novo lote com zero eventos',flush=True)
