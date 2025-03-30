import asyncio
import json
from pprint import pprint
from typing import Dict, Optional

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from typing import Dict, Any, Callable, Optional

from toolregistry import Tool, ToolRegistry


class MCPToolWrapper:
    """Wrapper class providing both async and sync versions of MCP tool calls."""

    def __init__(self, url: str = None, name: str = None, params: list = None):
        self.url = url
        self.name = name
        self.params = params or []

    async def call_async(self, **kwargs):
        """Async implementation of MCP tool call"""
        if not self.url or not self.name:
            raise ValueError("URL and name must be set before calling")

        try:
            async with sse_client(self.url) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    tool = next((t for t in tools.tools if t.name == self.name), None)
                    if not tool:
                        raise ValueError(f"Tool {self.name} not found on server")

                    validated_params = {}
                    for param_name, _ in tool.inputSchema.get("properties", {}).items():
                        if param_name in kwargs:
                            validated_params[param_name] = kwargs[param_name]

                    return await session.call_tool(self.name, validated_params)
        except Exception as e:
            print(f"Error calling tool {self.name}: {str(e)}")
            raise

    def call_sync(self, **kwargs):
        """Synchronous implementation of MCP tool call"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.call_async(**kwargs))

    def __call__(self, *args, **kwargs):
        """Make the wrapper directly callable, using sync version by default.
        Handles both positional and keyword arguments.
        Positional args are mapped to params in order, keyword args are passed directly.
        """
        if args:
            if not self.params:
                raise ValueError("Tool parameters not initialized")
            if len(args) > len(self.params):
                raise TypeError(
                    f"Expected at most {len(self.params)} positional arguments, got {len(args)}"
                )
            # Map positional args to their corresponding parameter names
            for i, arg in enumerate(args):
                param_name = self.params[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"Parameter '{param_name}' passed both as positional and keyword argument"
                    )
                kwargs[param_name] = arg
        return self.call_sync(**kwargs)


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
        wrapper = MCPToolWrapper(
            url=url,
            name=name,
            params=(
                list(input_schema.get("properties", {}).keys()) if input_schema else []
            ),
        )
        return cls(
            name=name,
            description=description,
            parameters=input_schema,
            callable=wrapper,
            is_async=False,
        )

    def run(self, **kwargs):
        """Synchronous execution of the tool"""
        return self.callable(**kwargs)


class MCPIntegration:
    """Handles integration with MCP server for tool registration."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def register_mcp_tools_async(self, server_url: str):
        """
        Async implementation to register all tools from an MCP server.

        Args:
            server_url (str): URL of the MCP server (e.g. "http://localhost:8000/mcp/sse")
        """
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
                    mcptool_from_json = MCPTool.from_tool_json(
                        name=tool.name,
                        description=tool.description,
                        input_schema=tool.inputSchema,
                        url=server_url,
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

        if loop.is_running():
            # if event loop is already running, use run_coroutine_threadsafe
            future = asyncio.run_coroutine_threadsafe(
                self.register_mcp_tools_async(server_url), loop
            )
            return future.result()
        else:
            return loop.run_until_complete(self.register_mcp_tools_async(server_url))
