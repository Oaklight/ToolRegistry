from mcp.server.fastmcp import FastMCP

# Create a calculator test server
mcp = FastMCP(
    "Calculator Test Server", sse_path="/mcp/sse", message_path="/mcp/messages/"
)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract two numbers"""
    return a - b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b


@mcp.tool()
def divide(a: int, b: int) -> float:
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
