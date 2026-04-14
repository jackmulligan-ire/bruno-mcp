"""Entry point for running the Bruno MCP server."""

from bruno_mcp.server import MCPServer


def main():
    server = MCPServer.create()
    server.mcp.run()


if __name__ == "__main__":
    main()
