"""Controle e evidência via MCP oficial do Activator histórico."""
import argparse,asyncio,json
from datetime import datetime,timezone
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from client import ROOT,credential
from evidence import write_json
p=argparse.ArgumentParser();p.add_argument('--discover',action='store_true');p.add_argument('--enable',action='store_true');p.add_argument('--stop',action='store_true');args=p.parse_args()
assert not(args.enable and args.stop)
async def main():
 c=json.loads((ROOT/'.local/fabric-environment.json').read_text())
 s=json.loads((ROOT/'.local/phase2-streaming/binding.json').read_text())
 old=json.loads((ROOT/'.local/m10-api/binding.json').read_text())
 common={'artifactId':old['activator']['id'],'workspaceId':c['workspace_id']}
 url=f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{c['workspace_id']}/reflexes/{old['activator']['id']}"
 token=credential.get_token('https://api.fabric.microsoft.com/.default').token
 async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+token},timeout=60) as http:
  async with streamable_http_client(url,http_client=http) as (read,write):
   async with ClientSession(read,write) as session:
    await session.initialize()
    tools=(await session.list_tools()).tools
    if args.discover:
     print(json.dumps([{'name':t.name,'schema':t.input_schema} for t in tools if t.name in {'get_rule','get_event_schema','get_source_schema','get_rule_details'}],default=str));print('Tools:',[t.name for t in tools]);return
    listing=await session.call_tool('list_rules',{'listRulesParams':common});assert not listing.is_error
    rule=next(r for r in listing.structured_content['rules'] if r['uniqueIdentifier']==s['rule_id'])
    write_json(ROOT/'.local/phase2-streaming/current-rule.private.json',rule)
    if args.enable and not rule['isRunning']:
     action=await session.call_tool('start_rule',{'startRuleParams':{**common,'ruleId':s['rule_id']}});assert not action.is_error,action
    if args.stop and rule['isRunning']:
     action=await session.call_tool('stop_rule',{'stopRuleParams':{**common,'ruleId':s['rule_id']}});assert not action.is_error,action
    listing=await session.call_tool('list_rules',{'listRulesParams':common});assert not listing.is_error
    rule=next(r for r in listing.structured_content['rules'] if r['uniqueIdentifier']==s['rule_id'])
    if args.enable:assert rule['isRunning']
    if args.stop:assert not rule['isRunning']
    write_json(ROOT/'evidence/phase2/streaming/rule-state.json',{'rule_id':s['rule_id'],'rule_running':rule['isRunning'],'checked_at_utc':datetime.now(timezone.utc).isoformat()})
    history=await session.call_tool('get_activations_for_rule',{'getActivationsParams':{**common,'ruleId':s['rule_id'],'maxResults':100}})
    if history.is_error:
     write_json(ROOT/'.local/phase2-streaming/activation-error.private.json',history.model_dump())
     print(json.dumps({'rule_running':rule['isRunning'],'activation_history_error':history.model_dump()},default=str),flush=True)
     return
    write_json(ROOT/'.local/phase2-streaming/activations.private.json',history.model_dump())
    report={'rule_id':s['rule_id'],'lab_run_id':s['lab_run_id'],'rule_running':rule['isRunning'],'activation_count':history.structured_content['totalCount'],'checked_at_utc':datetime.now(timezone.utc).isoformat()}
    write_json(ROOT/'evidence/phase2/streaming/activator-status.json',report);print(json.dumps(report),flush=True)
asyncio.run(main())
