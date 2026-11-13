"""MCP oficial do Activator: historico real e encerramento verificavel do lab."""
import argparse
import asyncio
import json
from datetime import datetime, timezone

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from client import ROOT, credential, request

parser = argparse.ArgumentParser()
parser.add_argument('--shutdown', action='store_true')
args = parser.parse_args()


async def main():
    folder = ROOT / '.local/m10-api'
    config = json.loads((ROOT / '.local/fabric-environment.json').read_text())
    binding = json.loads((folder / 'binding.json').read_text())
    ready = json.loads((folder / 'activator-ready.json').read_text())
    workspace, artifact, rule = config['workspace_id'], binding['activator']['id'], binding['activator']['rule_id']
    url = f'https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspace}/reflexes/{artifact}'
    token = credential.get_token('https://api.fabric.microsoft.com/.default').token
    common = {'artifactId': artifact, 'workspaceId': workspace}
    async with httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + token}, timeout=60) as http:
        async with streamable_http_client(url, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                available = {tool.name for tool in (await session.list_tools()).tools}
                assert {'list_rules', 'get_activations_for_rule', 'stop_rule'} <= available
                listing = await session.call_tool('list_rules', {'listRulesParams': common})
                assert not listing.is_error
                current = next(r for r in listing.structured_content['rules'] if r['uniqueIdentifier'] == rule)
                if args.shutdown and current['isRunning']:
                    stopped = await session.call_tool('stop_rule', {'stopRuleParams': {**common, 'ruleId': rule}})
                    assert not stopped.is_error
                    listing = await session.call_tool('list_rules', {'listRulesParams': common})
                    assert not listing.is_error
                    current = next(r for r in listing.structured_content['rules'] if r['uniqueIdentifier'] == rule)
                history = await session.call_tool('get_activations_for_rule', {'getActivationsParams': {
                    **common, 'ruleId': rule, 'maxResults': 100}})
                (folder / 'rules-status.json').write_text(json.dumps(listing.model_dump(), default=str, indent=2))
                (folder / 'activations.json').write_text(json.dumps(history.model_dump(), default=str, indent=2))
                assert not history.is_error, 'Historico indisponivel; nao confundir com zero ativacoes'
                report = {'rule_running': current['isRunning'], 'activation_count': history.structured_content['totalCount'],
                    'activations': [{'activationTime': a['activationTime'], 'actionType': a['properties'].get('System.ActionType')}
                                    for a in history.structured_content['activations']],
                    'checked_at_utc': datetime.now(timezone.utc).isoformat()}
    if args.shutdown:
        assert report['rule_running'] is False
        base = f"workspaces/{workspace}/eventstreams/{binding['eventstream']['id']}"
        topology = request('GET', base + '/topology').json()
        if not all(n['status'] == 'Paused' for n in topology['destinations']):
            request('POST', base + '/pause')
        for attempt in range(20):
            topology = request('GET', base + '/topology').json()
            if all(n['status'] == 'Paused' for n in topology['destinations']):
                break
            assert attempt < 19, 'Retomar observacao; destinos ainda nao pausados'
            await asyncio.sleep(15)
        assert all(n['status'] == 'Paused' or n['type'] == 'CustomEndpoint' for n in topology['sources'])
        report['eventstream_destinations_paused'] = True
        report['custom_endpoint_status'] = [n['status'] for n in topology['sources'] if n['type'] == 'CustomEndpoint']
        report['custom_endpoint_note'] = 'Endpoint passivo pode permanecer Running; emissor finito encerrado.'
        out = ROOT / 'evidence/fabric/streaming' / ready['lab_run_id']
        out.mkdir(parents=True, exist_ok=True)
        (out / 'mcp-shutdown-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


asyncio.run(main())
