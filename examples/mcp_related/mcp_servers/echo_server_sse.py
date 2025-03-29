from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Echo SSE", sse_path="/mcp/sse", message_path="/mcp/messages/")


@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"


@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"


app = mcp.sse_app()
