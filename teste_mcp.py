import asyncio

from langchain_mcp_adapters.client import MultiServerMCPClient


MCP_CONFIG = {
    "sigtap": {
        "command": "python",
        "args": [
            "src/mcp/sigtap_server.py"
        ],
        "transport": "stdio",
    }
}


async def main():

    client = MultiServerMCPClient(MCP_CONFIG)

    print("Conectando MCP...")

    tools = await client.get_tools()

    print("Ferramentas encontradas:")
    for tool in tools:
        print("-", tool.name)


asyncio.run(main())