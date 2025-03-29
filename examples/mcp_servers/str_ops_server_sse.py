from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

# Create a string manipulation test server
mcp = FastMCP("String Test Server")


@mcp.tool()
def reverse_string(text: str) -> str:
    """Reverse a string"""
    return text[::-1]


@mcp.tool()
def count_words(text: str) -> int:
    """Count words in a string"""
    return len(text.split())


@mcp.tool()
def uppercase(text: str) -> str:
    """Convert string to uppercase"""
    return text.upper()


@mcp.tool()
def lowercase(text: str) -> str:
    """Convert string to lowercase"""
    return text.lower()


@mcp.resource("strings://greetings/hello")
def get_hello() -> str:
    """Get a hello greeting"""
    return "Hello, world!"


@mcp.resource("strings://greetings/goodbye")
def get_goodbye() -> str:
    """Get a goodbye greeting"""
    return "Goodbye, world!"


# Create SSE endpoint
app = Starlette()
app.mount("/mcp/sse", mcp.sse_app())
