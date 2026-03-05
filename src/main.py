import os
import asyncio

from dotenv import load_dotenv
from dedalus_mcp import MCPServer
from dedalus_mcp.auth import Connection, SecretKeys

from src.tools import tools

load_dotenv()

# --- DAuth Connection ---
# Carta uses OAuth 2.0 Authorization Code Flow. Run `python -m src.oauth_helper`
# to obtain a Bearer token, which is stored as CARTA_ACCESS_TOKEN. DAuth keeps
# the token inside a sealed enclave — this server never sees the raw secret.

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
