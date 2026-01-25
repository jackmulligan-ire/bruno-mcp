"""Entry point for running the Bruno MCP server."""

from bruno_mcp.server import MCPServer

if __name__ == "__main__":
    server = MCPServer.create()
    server.mcp.run()
