"""Valida somente initialize/list_tools: nao executa operacoes no Fabric."""
import asyncio
import json
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[2]


async def main():
    env = dict(os.environ, AZURE_CONFIG_DIR=str(ROOT / '.local/azure'))
    parameters = StdioServerParameters(
        command='node',
        args=[str(ROOT / '.local/fabric-mcp/node_modules/@microsoft/fabric-mcp/index.js'),
              'server', 'start', '--mode', 'all', '--namespace', 'core',
              '--namespace', 'jobs', '--namespace', 'onelake'],
        env=env,
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            result = await session.list_tools()
            report = {
                'server': initialized.server_info.model_dump(),
                'protocol_initialized': True,
                'authenticated_fabric': False,
                'tools': [tool.name for tool in result.tools],
            }
            target = ROOT / '.local/fabric-mcp-probe.json'
            target.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
