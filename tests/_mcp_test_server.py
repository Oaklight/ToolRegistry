"""Minimal MCP server for testing MCPClient transports.

This script creates a lightweight MCP server using the official mcp SDK
with a few simple tools for use in integration tests. It supports stdio,
sse, and streamable-http transports via command-line arguments.

Usage:
    python _mcp_test_server.py                          # stdio (default)
    python _mcp_test_server.py --transport sse --port 0
    python _mcp_test_server.py --transport streamable-http --port 0
"""

import argparse
import json

try:
    from mcp.server.mcpserver import MCPServer as _ServerClass

    _MCP_V2 = True
except ImportError:
    from mcp.server.fastmcp import FastMCP as _ServerClass

    _MCP_V2 = False


def create_server(host: str = "127.0.0.1", port: int = 8000):
    """Create a minimal MCP server with test tools.

    Args:
        host: Host to bind to for network transports.
        port: Port to bind to for network transports.

    Returns:
        Configured server instance.
    """
    if _MCP_V2:
        mcp = _ServerClass("test-server")
    else:
        mcp = _ServerClass("test-server", host=host, port=port)

    @mcp.tool()
    def add(a: int, b: int) -> str:
        """Add two integers and return the result as JSON."""
        return json.dumps({"result": a + b})

    @mcp.tool()
    def echo(message: str) -> str:
        """Echo back the given message."""
        return message

    @mcp.tool()
    def greet(name: str = "World") -> str:
        """Return a greeting message."""
        return f"Hello, {name}!"

    @mcp.tool()
    def slow_tool(seconds: float = 5.0) -> str:
        """Sleep for the given duration, then return. Used to test timeout."""
        import time

        time.sleep(seconds)
        return f"slept {seconds}s"

    return mcp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    mcp = create_server(host=args.host, port=args.port)

    if _MCP_V2:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
    else:
        mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
