"""Math server using the `fastmcp` standalone library directly.

This module implements a math server that directly uses the fastmcp
standalone library without any additional dependencies.
"""

import argparse

from fastmcp import FastMCP

# Common server configuration
server_name = "Math Server"
mcp = FastMCP(server_name)


# Register all math tools
@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract two numbers"""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide two numbers"""
    return a / b


# Register all math resources
@mcp.resource("math://constants/pi")
def get_pi() -> float:
    """Get the value of pi"""
    return 3.141592653589793


@mcp.resource("math://constants/e")
def get_e() -> float:
    """Get the value of e"""
    return 2.718281828459045


if __name__ == "__main__":
    """Create a unified math server with all tools and resources"""
    parser = argparse.ArgumentParser(description="Math Server")
    parser.add_argument(
        "--mode",
        type=str,
        default="stdio",
        choices=["stdio", "sse"],
        help="Server transport mode: stdio, sse, ws or http",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port number for network modes"
    )
    args = parser.parse_args()

    # Create appropriate app based on mode
    if args.mode == "stdio":
        mcp.run()
    elif args.mode == "sse":
        mcp.run(
            transport="sse",
            host="localhost",
            port=args.port,
        )
