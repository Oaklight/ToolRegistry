import json
from typing import Any, Callable, Dict, List, Optional, Union

from .tool import Tool


class ToolRegistry:
    """Central registry for managing tools (functions) and their metadata.

    Provides functionality to:
        - Register and manage tools
        - Merge multiple registries
        - Execute tool calls
        - Generate tool schemas
        - Interface with MCP servers

    Attributes:
        _tools (Dict[str, Tool]): Internal dictionary mapping tool names to Tool instances.
    """

    def __init__(self) -> None:
        """Initialize an empty ToolRegistry.

        Creates an empty dictionary to store tools.

        Attributes:
            _tools (Dict[str, Tool]): Internal dictionary to store registered tools.
        """
        self._tools: Dict[str, Tool] = {}

    def __len__(self) -> int:
        """Return the number of registered tools.

        Returns:
            int: Count of registered tools.
        """
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if a tool with the given name is registered.

        Args:
            name (str): Name of the tool to check.

        Returns:
            bool: True if tool is registered, False otherwise.
        """
        return name in self._tools

    def register(
        self, tool_or_func: Union[Callable, Tool], description: Optional[str] = None
    ):
        """Register a tool, either as a function or Tool instance.

        Args:
            tool_or_func (Union[Callable, Tool]): The tool to register, either as a function or Tool instance.
            description (Optional[str]): Description for function tools. If not provided, the function's docstring will be used.
        """
        if isinstance(tool_or_func, Tool):
            self._tools[tool_or_func.name] = tool_or_func
        else:
            tool = Tool.from_function(tool_or_func, description=description)
            self._tools[tool.name] = tool

    def merge(self, other: "ToolRegistry", keep_existing: bool = False):
        """Merge tools from another ToolRegistry into this one.

        Handles name conflicts according to keep_existing parameter.

        Args:
            other (ToolRegistry): The ToolRegistry to merge from.
            keep_existing (bool): If True, preserves existing tools on name conflicts.

        Raises:
            TypeError: If other is not a ToolRegistry instance.
        """
        if not isinstance(other, ToolRegistry):
            raise TypeError("Can only merge with another ToolRegistry instance.")

        if keep_existing:
            for name, tool in other._tools.items():
                if name not in self._tools:
                    self._tools[name] = tool
        else:
            self._tools.update(other._tools)

    def register_mcp_tools(self, server_url: str):
        """Register all tools from an MCP server (synchronous entry point).

        Requires the [mcp] extra to be installed.

        Args:
            server_url (str): URL of the MCP server.

        Raises:
            ImportError: If [mcp] extra is not installed.
        """
        try:
            from .mcp_integration import MCPIntegration

            mcp = MCPIntegration(self)
            return mcp.register_mcp_tools(server_url)
        except ImportError:
            raise ImportError(
                "MCP integration requires the [mcp] extra. "
                "Install with: pip install toolregistry[mcp]"
            )

    async def register_mcp_tools_async(self, server_url: str):
        """Async implementation to register all tools from an MCP server.

        Requires the [mcp] extra to be installed.

        Args:
            server_url (str): URL of the MCP server.

        Raises:
            ImportError: If [mcp] extra is not installed.
        """
        try:
            from .mcp_integration import MCPIntegration

            mcp = MCPIntegration(self)
            return await mcp.register_mcp_tools_async(server_url)
        except ImportError:
            raise ImportError(
                "MCP integration requires the [mcp] extra. "
                "Install with: pip install toolregistry[mcp]"
            )

    def register_openapi_tools(self, spec_url: str, base_url: Optional[str] = None):
        """Register all tools from an OpenAPI specification (synchronous entry point).

        Requires the [openapi] extra to be installed.

        Args:
            spec_url (str): URL or path to the OpenAPI specification.
            base_url (Optional[str]): Optional base URL to use if the spec does not provide a server.

        Raises:
            ImportError: If [openapi] extra is not installed.
        """
        try:
            from .openapi_integration import OpenAPIIntegration

            openapi = OpenAPIIntegration(self)
            return openapi.register_openapi_tools(spec_url, base_url)
        except ImportError:
            raise ImportError(
                "OpenAPI integration requires the [openapi] extra. "
                "Install with: pip install toolregistry[openapi]"
            )

    async def register_openapi_tools_async(
        self, spec_url: str, base_url: Optional[str] = None
    ):
        """Async implementation to register all tools from an OpenAPI specification.

        Requires the [openapi] extra to be installed.

        Args:
            spec_url (str): URL or path to the OpenAPI specification.
            base_url (Optional[str]): Optional base URL to use if the spec does not provide a server.

        Raises:
            ImportError: If [openapi] extra is not installed.
        """
        try:
            from .openapi_integration import OpenAPIIntegration

            openapi = OpenAPIIntegration(self)
            return await openapi.register_openapi_tools_async(spec_url, base_url)
        except ImportError:
            raise ImportError(
                "OpenAPI integration requires the [openapi] extra. "
                "Install with: pip install toolregistry[openapi]"
            )

    def get_available_tools(self) -> List[str]:
        """List all registered tools.

        Returns:
            List[str]: A list of tool names.
        """

        return list(self._tools.keys())

    def get_tools_json(self, tool_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get the JSON representation of all registered tools, following JSON Schema.

        Args:
            tool_name (Optional[str]): Optional name of specific tool to get schema for.

        Returns:
            List[Dict[str, Any]]: A list of tools in JSON format, compliant with JSON Schema.
        """
        if tool_name:
            target_tool = self.get_tool(tool_name)
            tools = [target_tool] if target_tool else []
        else:
            tools = list(self._tools.values())

        return [tool.get_json_schema() for tool in tools]

    def get_tool(self, tool_name: str) -> Optional[Tool]:
        """Get a tool by its name.

        Args:
            tool_name (str): Name of the tool to retrieve.

        Returns:
            Optional[Tool]: The tool, or None if not found.
        """
        tool = self._tools.get(tool_name)
        return tool

    def get_callable(self, tool_name: str) -> Optional[Callable[..., Any]]:
        """Get a callable function by its name.

        Args:
            tool_name (str): Name of the function to retrieve.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        tool = self.get_tool(tool_name)
        return tool.callable if tool else None

    def execute_tool_calls(self, tool_calls: List[Any]) -> Dict[str, str]:
        """Execute tool calls with optimized parallel/sequential execution.

        Execution strategy:
            - Sequential for 1-2 tool calls (avoids thread pool overhead)
            - Parallel for 3+ tool calls (improves performance)

        Args:
            tool_calls (List[Any]): List of tool call objects.

        Returns:
            Dict[str, str]: Dictionary mapping tool call IDs to execution results.

        Raises:
            Exception: If any tool execution fails.
        """

        def process_tool_call(tool_call):
            try:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tool_call_id = tool_call.id

                # Get the tool from registry
                tool = self.get_tool(function_name)
                if tool:
                    tool_result = tool.run(function_args)
                else:
                    tool_result = f"Error: Tool '{function_name}' not found"
            except Exception as e:
                tool_result = f"Error executing {function_name}: {str(e)}"
            return (tool_call_id, tool_result)

        tool_responses = {}

        if len(tool_calls) > 2:
            # only use concurrency if more than 2 tool calls at a time
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(process_tool_call, tool_call)
                    for tool_call in tool_calls
                ]
                for future in concurrent.futures.as_completed(futures):
                    tool_call_id, tool_result = future.result()
                    tool_responses[tool_call_id] = tool_result
        else:
            for tool_call in tool_calls:
                tool_call_id, tool_result = process_tool_call(tool_call)
                tool_responses[tool_call_id] = tool_result

        return tool_responses

    def recover_tool_call_assistant_message(
        self, tool_calls: List[Any], tool_responses: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Construct assistant messages from tool call results.

        Creates a conversation history with:
            - Assistant tool call requests
            - Tool execution responses

        Args:
            tool_calls (List[Any]): List of tool call objects.
            tool_responses (Dict[str, str]): Dictionary of tool call IDs to results.

        Returns:
            List[Dict[str, Any]]: List of message dictionaries in conversation format.
        """
        messages = []
        for tool_call in tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "content": f"{tool_call.function.name} --> {tool_responses[tool_call.id]}",
                    "tool_call_id": tool_call.id,
                }
            )
        return messages

    def __repr__(self):
        """Return the JSON representation of the registry for debugging purposes.

        Returns:
            str: JSON string representation of the registry.
        """
        return json.dumps(self.get_tools_json(), indent=2)

    def __str__(self):
        """Return the JSON representation of the registry as a string.

        Returns:
            str: JSON string representation of the registry.
        """
        return json.dumps(self.get_tools_json(), indent=2)

    def __getitem__(self, key: str) -> Optional[Callable[..., Any]]:
        """Enable key-value access to retrieve callables.

        Args:
            key (str): Name of the function.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        return self.get_callable(key)
