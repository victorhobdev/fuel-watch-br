"""Regra real de laboratorio: transicao de preco aciona somente auditoria SQL."""
import base64
import copy
import json
import requests
from uuid import uuid4

from client import ROOT, definition_operation, request
from warehouse import connect, results

folder = ROOT / '.local/m10-api'
bindings = folder / 'binding.json'
s = json.loads(bindings.read_text())
c = json.loads((ROOT / '.local/fabric-environment.json').read_text())
w = c['workspace_id']
run = 'daf2320c-b0bc-4eef-b908-a2dd80939088'
with connect(c) as connection:
    results(connection.cursor().execute("IF SCHEMA_ID('lab_m10') IS NULL EXEC('CREATE SCHEMA lab_m10'); "
        "IF OBJECT_ID('lab_m10.alert_audit') IS NULL CREATE TABLE lab_m10.alert_audit "
        "(pipeline_run_id varchar(36),lab_run_id varchar(36),recorded_at_utc datetime2(6),is_synthetic bit);"))
if not s.get('alert_pipeline_id'):
    items = request('GET', f'workspaces/{w}/items').json()['value']
    matches = [x for x in items if x['displayName'] == 'pl_m10_alert_audit']
    if matches:
        s['alert_pipeline_id'] = matches[0]['id']
    else:
        parent = definition_operation(f"workspaces/{w}/dataPipelines/{c['pipeline_id']}/getDefinition")
        body = json.loads(base64.b64decode(next(p for p in parent['definition']['parts'] if p['path'] == 'pipeline-content.json')['payload']))
        activity = copy.deepcopy(body['properties']['activities'][0])
        activity['name'] = 'Record_Synthetic_Alert'
        activity['typeProperties']['scripts'] = [{'type': 'Query', 'text': {'type': 'Expression',
            'value': "@concat('INSERT INTO lab_m10.alert_audit VALUES (''',pipeline().RunId,''',''" + run + "'',CAST(SYSUTCDATETIME() AS datetime2(6)),1);')"}}]
        payload = {'properties': {'activities': [activity], 'parameters': {}}}
        part = {'path': 'pipeline-content.json', 'payloadType': 'InlineBase64',
                'payload': base64.b64encode(json.dumps(payload).encode()).decode()}
        created = definition_operation(f'workspaces/{w}/dataPipelines', {'displayName': 'pl_m10_alert_audit',
            'description': 'Synthetic Activator action only; never runs ANP pipeline', 'definition': {'parts': [part]}})
        s['alert_pipeline_id'] = created['id']
    bindings.write_text(json.dumps(s, indent=2))
base = f"workspaces/{w}/reflexes/{s['activator']['id']}"
definition = definition_operation(base + '/getDefinition')
(folder / 'before-rule.json').write_text(json.dumps(definition, indent=2))
part = next(p for p in definition['definition']['parts'] if p['path'] == 'ReflexEntities.json')
entities = json.loads(base64.b64decode(part['payload']))
assert not any(e.get('payload', {}).get('name') == 'Fuel Watch threshold 7' for e in entities), 'Regra ja existe: inspecionar antes de atualizar'
action_id, rule_id = str(uuid4()), str(uuid4())
def arg(name, value):
    return {'name': name, 'type': 'number' if isinstance(value, (int, float)) else 'string', 'value': value}
def step(name, rows):
    return {'name': name, 'id': str(uuid4()), 'rows': rows}
event = {'name': 'EventSelector', 'kind': 'Event', 'arguments': [{'name': 'event', 'type': 'complex',
    'kind': 'EventReference', 'arguments': [arg('entityId', s['activator']['source_event_entity_id'])]}]}
action = {'name': 'FabricItemBinding', 'kind': 'FabricItemInvocation', 'arguments': [
    arg('workspaceId', w), arg('itemId', s['alert_pipeline_id']), arg('itemType', 'Pipeline'), arg('jobType', 'Pipeline'),
    arg('fabricJobConnectionDocumentId', action_id), {'name': 'additionalInformation', 'type': 'array', 'values': []},
    {'name': 'parameters', 'type': 'array', 'values': []}]}
template = {'templateId': 'EventTrigger', 'templateVersion': '1.2.4', 'steps': [
    step('FieldsDefaultsStep', [event]), step('EventDetectStep', [
        {'name': 'EventFieldSelector', 'kind': 'EventField', 'arguments': [arg('fieldName', 'preco')]},
        {'name': 'NumberBecomes', 'kind': 'NumberBecomes', 'arguments': [arg('op', 'BecomesGreaterThan'), arg('value', 7.0)]}]),
    step('ActStep', [action])]}
entities.extend([{'uniqueIdentifier': action_id, 'type': 'fabricItemAction-v1', 'payload': {
    'name': 'Record synthetic alert', 'fabricItem': {'itemId': s['alert_pipeline_id'], 'workspaceId': w, 'itemType': 'Pipeline'}, 'jobType': 'Pipeline'}},
    {'uniqueIdentifier': rule_id, 'type': 'timeSeriesView-v1', 'payload': {'name': 'Fuel Watch threshold 7',
        'description': 'Synthetic controlled threshold; internal audit only', 'definition': {'type': 'Rule',
        'instance': json.dumps(template), 'settings': {'shouldRun': True, 'shouldApplyRuleOnUpdate': False}}}}])
part['payload'] = base64.b64encode(json.dumps(entities).encode()).decode()
definition['definition'].pop('format', None)
try:
    definition_operation(base + '/updateDefinition', {'definition': definition['definition']})
except requests.HTTPError as exc:
    (folder / 'rule-error.private.json').write_text(exc.response.text)
    print(exc.response.text, flush=True)
    raise
actual = definition_operation(base + '/getDefinition')
(folder / 'rule-readback.json').write_text(json.dumps(actual, indent=2))
found = json.loads(base64.b64decode(next(p for p in actual['definition']['parts'] if p['path'] == 'ReflexEntities.json')['payload']))
rule = next(e for e in found if e['uniqueIdentifier'] == rule_id)
assert rule['payload']['definition']['settings']['shouldRun']
s['activator']['rule_id'] = rule_id
bindings.write_text(json.dumps(s, indent=2))
(folder / 'activator-ready.json').write_text(json.dumps({'lab_run_id': run, 'rule_enabled_readback': True,
    'runtime_trigger_verified': False, 'rule_id': rule_id}, indent=2))
print('Rule definition enabled/readback verified; runtime trigger still pending', flush=True)
