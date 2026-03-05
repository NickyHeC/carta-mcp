import os
import asyncio

from dotenv import load_dotenv
from dedalus_mcp import MCPServer
from dedalus_mcp.auth import Connection, SecretKeys

from src.tools import tools

load_dotenv()

# --- DAuth Connection ---
# Carta uses OAuth 2.0 Bearer tokens. Obtain an access token via the client
# credentials flow (POST https://login.app.carta.com/o/access_token/) using
# your CARTA_CLIENT_ID and CARTA_CLIENT_SECRET, then store the resulting token
# as CARTA_ACCESS_TOKEN in your DAuth session.

carta_connection = Connection(
    name="carta",
    secrets=SecretKeys(token="CARTA_ACCESS_TOKEN"),
    base_url="https://api.carta.com",
    auth_header_format="Bearer {api_key}",
)

# --- Server ---

server = MCPServer(
    name="carta-mcp",
    connections=[carta_connection],
    authorization_server=os.getenv("DEDALUS_AS_URL", "https://as.dedaluslabs.ai"),
    streamable_http_stateless=True,
)


async def main() -> None:
    for tool_func in tools:
        server.collect(tool_func)
    await server.serve(port=8080)


if __name__ == "__main__":
    asyncio.run(main())
