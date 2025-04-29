"""Math server using `mcp.server.fastmcp` package.

This module implements a math server that uses the mcp.server.fastmcp
package for server-side SSE (Server-Sent Events) functionality.
"""

from mcp.server.fastmcp import FastMCP

# Create a calculator test server
mcp = FastMCP(
    "Calculator Test Server", sse_path="/mcp/sse", message_path="/mcp/messages/"
)


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


@mcp.resource("math://constants/pi")
def get_pi() -> float:
    """Get the value of pi"""
    return 3.141592653589793


@mcp.resource("math://constants/e")
def get_e() -> float:
    """Get the value of e"""
    return 2.718281828459045


# Create SSE endpoint
app = mcp.sse_app()
