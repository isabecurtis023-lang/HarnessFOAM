from harnessfoam.core.mcp_server import app

def main():
    # FastMCP owns the current MCP stdio transport and initialization flow.
    app.run(transport="stdio")

if __name__ == "__main__":
    main()
