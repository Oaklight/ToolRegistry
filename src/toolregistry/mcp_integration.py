import asyncio
import json
from pprint import pprint
from typing import Dict, Optional

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from typing import Dict, Any, Callable, Optional

from toolregistry import Tool, ToolRegistry


def _make_mcp_tool_wrapper(url, name) -> Callable[..., Any]:
    pass

    def wrapper():
        return 0

    return wrapper


class MCPTool(Tool):
    """Wrapper class for MCP tools that preserves original function metadata."""

    @classmethod
    def from_tool_json(
        cls,
        name: Optional[str],
        description: Optional[str],
        input_schema: Optional[Dict[str, Any]],
        url: str = None,
    ):
        """Create an MCPToolWrapper from a function."""

        func = _make_mcp_tool_wrapper(url, name)
        return cls(
            name=name,
            description=description,
            parameters=input_schema,
            callable=func,
            is_async=True,  # mcp functions are by nature async
        )


class MCPIntegration:
    """Handles integration with MCP server for tool registration."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._mcp_server_url: Optional[str] = None

    async def register_mcp_tools_async(self, server_url: str):
        """
        Async implementation to register all tools from an MCP server.

        Args:
            server_url (str): URL of the MCP server (e.g. "http://localhost:8000/mcp/sse")
        """
        self._mcp_server_url = server_url
        print(f"Connecting to MCP server at {server_url}")

        async with sse_client(server_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                print("Connected to server, initializing session...")
                await session.initialize()

                # Get available tools from server
                tools_response = await session.list_tools()
                print(f"Found {len(tools_response.tools)} tools on server")

                # Register each tool with a wrapper function
                for tool in tools_response.tools:
                    pprint(tool)
                    # print(json.dumps(convert_mcptool_to_json(tool), indent=2))
                    mcptool_from_json = MCPTool.from_tool_json(
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.inputSchema,
                    )

                    # Register the tool wrapper function
                    self.registry.register(mcptool_from_json)
                    print(f"Registered tool: {tool.name}")

    def register_mcp_tools(self, server_url: str):
        """
        Register all tools from an MCP server (synchronous entry point).

        Args:
            server_url (str): URL of the MCP server
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.register_mcp_tools_async(server_url))
