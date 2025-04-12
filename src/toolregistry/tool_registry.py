import json
from typing import Any, Callable, Dict, List, Optional, Set, Union

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

    def __init__(self, name: Optional[str] = "UnamedRegistry") -> None:
        """Initialize an empty ToolRegistry.

        This method initializes an empty ToolRegistry with a name and internal
        structures for storing tools and sub-registries.

        Args:
            name (Optional[str]): Name of the tool registry. Defaults to "UnamedRegistry".

        Attributes:
            name (str): Name of the tool registry.

        Notes:
            This class uses private attributes `_tools` and `_sub_registries` internally
            to manage registered tools and sub-registries. These are not intended for
            external use.
        """
        self.name = name
        self._tools: Dict[str, Tool] = {}
        self._sub_registries: Set = {}

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

    def _prefix_tools_namespace(self):
        """Add the registry name as a prefix to the names of tools in the registry.

        This method updates the names of tools in the `_tools` dictionary by prefixing
        them with the registry's name if they don't already have a prefix. Tools that
        already have a prefix retain their existing name.

        Side Effects:
            Updates the `_tools` dictionary with potentially modified tool names.

        Example:
            If the registry name is "MainRegistry":
            - A tool with the name "ToolA" will be updated to "MainRegistry.ToolA".
            - A tool with the name "OtherRegistry.ToolB" will remain unchanged.

        Raises:
            None
        """
        new_tools: Dict[str, Tool] = {}
        for tool in self._tools.values():
            # Check if the tool already has a prefix
            if "." not in tool.name:
                # Add registry name as prefix if no existing prefix
                tool.name = f"{self.name}.{tool.name}"
            new_tools[tool.name] = tool
        self._tools = new_tools

    def merge(self, other: "ToolRegistry", keep_existing: bool = False):
        """Merge tools from another ToolRegistry into this one.

        Replaces the current registry with a new registry object.
        Tools keep their original prefixes from first merge and won't get additional prefixes.

        Args:
            other (ToolRegistry): The ToolRegistry to merge from.
            keep_existing (bool): If True, preserves existing tools on name conflicts.

        Raises:
            TypeError: If other is not a ToolRegistry instance.
        """
        if not isinstance(other, ToolRegistry):
            raise TypeError("Can only merge with another ToolRegistry instance.")

        # Create a new registry object
        new_registry = ToolRegistry()

        # Merge sub registries
        new_registry._sub_registries.update(self._sub_registries)
        new_registry._sub_registries.update(other._sub_registries)
        new_registry._sub_registries.update([self.name, other.name])

        # Only prefix tools that don't already have a prefix
        self._prefix_tools_namespace()
        other._prefix_tools_namespace()

        # Merge tools
        if keep_existing:
            for name, tool in other._tools.items():
                if name not in self._tools:
                    new_registry._tools[name] = tool
            new_registry._tools.update(self._tools)
        else:
            new_registry._tools.update(self._tools)
            new_registry._tools.update(other._tools)

        # Replace the current registry with the new one
        self.__dict__.update(new_registry.__dict__)

    def spinoff(self, prefix: str) -> "ToolRegistry":
        """Spin off tools with the specified prefix into a new registry.

        This method creates a new ToolRegistry, transferring tools that belong
        to the specified prefix to it, and removing them from the current registry.

        Args:
            prefix (str): Prefix to identify tools to spin off.

        Returns:
            ToolRegistry: A new registry containing the spun-off tools.

        Raises:
            ValueError: If no tools with the specified prefix are found.
        """
        # Filter tools with the specified prefix
        spun_off_tools = {
            name: tool
            for name, tool in self._tools.items()
            if name.startswith(f"{prefix}.")
        }

        if not spun_off_tools:
            raise ValueError(f"No tools with prefix '{prefix}' found in the registry.")

        # Create a new registry for the spun-off tools
        new_registry = ToolRegistry(name=prefix)
        new_registry._tools = {
            name[len(prefix) + 1 :]: tool  # Remove prefix from spun-off tool names
            for name, tool in spun_off_tools.items()
        }

        # Remove the spun-off tools from the current registry
        self._tools = {
            name: tool
            for name, tool in self._tools.items()
            if not name.startswith(f"{prefix}.")
        }

        # Remove the prefix from sub-registries if it exists
        self._sub_registries.discard(prefix)

        return new_registry

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
