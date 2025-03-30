import asyncio
import json
from pprint import pprint
from typing import Dict, Optional

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Tool as MCPTool

from .tool_registry import ToolRegistry

from typing import Dict, Any


def convert_mcptool_to_json(tool: MCPTool) -> Dict:
    """
    Convert a Tool object to the desired JSON format.

    Args:
        tool: A dictionary representing the Tool object with keys 'name', 'description', and 'inputSchema'.

    Returns:
        A dictionary in the desired JSON format.
    """
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": tool.inputSchema.get("properties", {}),
                "required": tool.inputSchema.get("required", []),
                "additionalProperties": False,
            },
        },
    }


def parse_mcp_tool_parameters(tool_params: Dict):
    tool_params = vars(tool_params)
    required_params = tool_params.required
    pass


def parse_mcp_tool(mcp_tool: MCPTool):
    tool_name = mcp_tool.name
    tool_description = mcp_tool.description
    tool_parameters: Dict = mcp_tool.parameters

    pass


class MCPIntegration:
    """Handles integration with MCP server for tool registration."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._mcp_server_url: Optional[str] = None

    # def _create_mcp_tool_wrapper(self, tool_name: str, server_url: str):
    #     """Create an async wrapper function for an MCP tool."""

    #     async def tool_wrapper(**params):
    #         """Wrapper function for MCP tool"""
    #         try:
    #             async with sse_client(server_url) as (rs, ws):
    #                 async with ClientSession(rs, ws) as s:
    #                     await s.initialize()
    #                     # Get tool schema to validate params
    #                     tools = await s.list_tools()

    #                     return await s.call_tool(tool_name, params)
    #         except Exception as e:
    #             print(f"Error calling tool {tool_name}: {str(e)}")
    #             raise

    #     # Set the wrapper's name to match the original tool name
    #     tool_wrapper.__name__ = tool_name
    #     return tool_wrapper

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
                    print(json.dumps(convert_mcptool_to_json(tool), indent=2))
                    # wrapper = (
                    #     tool.name, self._mcp_server_url
                    # )
                #     self.registry.register(
                #         wrapper,
                #         description=tool.description,
                #     )
                #     print(f"Registered tool: {tool.name}")

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
