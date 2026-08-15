# 2026-08-15 | Gemini 3.5 Flash (Medium)
import asyncio
from harnessfoam.core.mcp_server import app
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions

async def async_main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="HarnessFOAM-MCP",
                server_version="0.1.0",
                capabilities=app.get_capabilities(),
            ),
        )

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
