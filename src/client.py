"""
Test client for the Carta MCP server.

Start the server first:
    python -m src.main

Then run this script to verify your tools work:
    python -m src.client
"""

import asyncio
from dedalus_mcp.client import MCPClient


async def main() -> None:
    client = await MCPClient.connect("http://127.0.0.1:8080/mcp")

    tools = await client.list_tools()
    print("Available tools:", [t.name for t in tools.tools])

    # --- Quick smoke tests (read-only) ---

    result = await client.call_tool("list_issuers", {"page_size": 5})
    print("\nlist_issuers:", result.content[0].text)

    result = await client.call_tool("list_investor_firms", {"page_size": 5})
    print("\nlist_investor_firms:", result.content[0].text)

    result = await client.call_tool("list_portfolios", {"page_size": 5})
    print("\nlist_portfolios:", result.content[0].text)

    result = await client.call_tool("get_current_user", {})
    print("\nget_current_user:", result.content[0].text)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
