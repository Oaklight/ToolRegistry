from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette

mcp = FastMCP("Echo SSE")


@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"


@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"


app = Starlette(routes=[])
app.mount("/mcp", mcp.sse_app())
