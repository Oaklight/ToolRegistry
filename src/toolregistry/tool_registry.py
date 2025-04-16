import json
import random
import string
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union

from deprecated import deprecated  # type: ignore

from .tool import Tool
from .utils import normalize_tool_name


class ToolRegistry:
    """Central registry for managing tools (functions) and their metadata.

    This class provides functionality to register, manage, and execute tools,
    as well as to interface with MCP servers, OpenAPI endpoints, and generate tool schemas.

    Attributes:
        name (str): The name of the tool registry.

    Notes:
        Private attributes are used internally to manage registered tools and
        sub-registries. These attributes are not intended for external use.
    """

    def __init__(self, name: Optional[str] = None) -> None:
        """Initialize an empty ToolRegistry.

        This method initializes an empty ToolRegistry with a name and internal
        structures for storing tools and sub-registries.

        Args:
            name (Optional[str]): Name of the tool registry. Defaults to a random "reg_<4-char>" string. For instance, "reg_1a3c".

        Attributes:
            name (str): Name of the tool registry.

        Notes:
            This class uses private attributes `_tools` and `_sub_registries` internally
            to manage registered tools and sub-registries. These are not intended for
            external use.
        """
        if name is None:
            name = f"reg_{''.join(random.sample(string.hexdigits.lower(), 4))}"
        self.name = name
        self._tools: Dict[str, Tool] = {}
        self._sub_registries: Set[str] = set()

    def _find_sub_registries(self) -> Set:
        """
        Find sub-registries within the tools registered in this registry.

        This method identifies sub-registries by examining the names of tools
        and determining prefixes separated by a dot (`.`). For example, a tool
        named `calculator.add` would indicate that `calculator` is
        a sub-registry.

        Returns:
            Set: A set of strings representing sub-registry prefixes found
                within the registered tool names.

        Example:
            If `_tools` contains: {"a.tool1", "b.tool2", "tool3"}, this
            method will return {"a", "b"}.
        """
        return {
            tool_name.split(".", 1)[0]
            for tool_name in self._tools.keys()
            if "." in tool_name
        }

    def _update_sub_registries(self) -> None:
        """
        Update the internal set of sub-registries based on the registered tools.

        This method calls `_find_sub_registries` to identify sub-registry prefixes
        and updates the private `_sub_registries` set accordingly.

        Side Effects:
            Modifies the `_sub_registries` attribute with the latest prefixes.

        Returns:
            None
        """
        self._sub_registries = self._find_sub_registries()

    def __contains__(self, name: str) -> bool:
        """Check if a tool with the given name is registered.

        Args:
            name (str): Name of the tool to check.

        Returns:
            bool: True if tool is registered, False otherwise.
        """
        return name in self._tools

    def register(
        self,
        tool_or_func: Union[Callable, Tool],
        description: Optional[str] = None,
        name: Optional[str] = None,
        namespace: Optional[str] = None,
    ):
        """Register a tool, either as a function, Tool instance, or static method.

        Args:
            tool_or_func (Union[Callable, Tool]): The tool to register, either as a function, Tool instance, or static method.
            description (Optional[str]): Description for function tools. If not provided, the function's docstring will be used.
            name (Optional[str]): Custom name for the tool. If not provided, defaults to function name for functions or tool.name for Tool instances.
            namespace (Optional[str]): Namespace for the tool. For static methods, defaults to class name if not provided.
        """
        if namespace:
            self._sub_registries.add(normalize_tool_name(namespace))

        if isinstance(tool_or_func, Tool):
            tool_or_func.update_namespace(namespace, force=True)
            self._tools[tool_or_func.name] = tool_or_func
        else:
            tool = Tool.from_function(
                tool_or_func, description=description, name=name, namespace=namespace
            )
            self._tools[tool.name] = tool

    def _prefix_tools_namespace(self, force: bool = False) -> None:
        """Add the registry name as a prefix to the names of tools in the registry.

        This method updates the names of tools in the `_tools` dictionary by prefixing
        them with the registry's name if they don't already have a prefix. Tools that
        already have a prefix retain their existing name.

        Args:
            force (bool): If True, forces the namespace update for all tools, even if they already have a prefix.
                If False, retains existing prefixes for tools that already have one.

        Side Effects:
            Updates the `_tools` dictionary with potentially modified tool names.

        Example:
            If the registry name is "MainRegistry":
            - A tool with the name "tool_a" will be updated to "main_registry.tool_a".
            - A tool with the name "other_registry.tool_b" will remain unchanged if force=False.
            - A tool with the name "other_registry.tool_b" will be updated to "main_registry.tool_b" if force=True.

        Raises:
            None
        """
        new_tools: Dict[str, Tool] = {}
        for tool in self._tools.values():
            tool.update_namespace(self.name, force=force)
            new_tools[tool.name] = tool
        self._tools = new_tools

    def merge(
        self,
        other: "ToolRegistry",
        keep_existing: bool = False,
        force_namespace: bool = False,
    ):
        """
        Merge tools from another ToolRegistry into this one.

        This method directly updates the current registry with tools from another
        registry, avoiding the need to create a new ToolRegistry object.

        Args:
            other (ToolRegistry): The ToolRegistry to merge from.
            keep_existing (bool): If True, preserves existing tools on name conflicts.
            force_namespace (bool): If True, forces updating tool namespaces by prefixing them with the registry name; if False, retains existing namespaces.

        Raises:
            TypeError: If other is not a ToolRegistry instance.
        """
        if not isinstance(other, ToolRegistry):
            raise TypeError("Can only merge with another ToolRegistry instance.")

        # Prefix tools in both registries
        self._prefix_tools_namespace()
        other._prefix_tools_namespace()

        # Merge tools based on the `keep_existing` flag
        if keep_existing:
            for name, tool in other._tools.items():
                if name not in self._tools:
                    self._tools[name] = tool
        else:
            self._tools.update(other._tools)

        if force_namespace:
            # update namespace if required after merge done
            self._prefix_tools_namespace(force=force_namespace)

        # Update sub-registries based on merged tools
        self._update_sub_registries()

    def reduce_namespace(self) -> None:
        """Remove the namespace from tools in the registry if there is only one sub-registry.

        This method checks if there is only one sub-registry remaining in the registry.
        If so, it removes the namespace prefix from all tools and clears the sub-registries.

        Side Effects:
            - Updates the `_tools` dictionary to remove namespace prefixes.
            - Clears the `_sub_registries` set if namespace flattening occurs.

        Example:
            If the registry contains tools with names like "calculator.add" and "calculator.subtract",
            and "calculator" is the only sub-registry, this method will rename the tools to "add" and "subtract".
        """
        if len(self._sub_registries) == 1:
            remaining_prefix = next(iter(self._sub_registries))
            self._tools = {
                name[len(remaining_prefix) + 1 :]: tool
                for name, tool in self._tools.items()
            }
            self._sub_registries.clear()

    def spinoff(self, prefix: str, retain_namespace: bool = False) -> "ToolRegistry":
        """Spin off tools with the specified prefix into a new registry.

        This method creates a new ToolRegistry, transferring tools that belong
        to the specified prefix to it, and removing them from the current registry.

        Args:
            prefix (str): Prefix to identify tools to spin off.
            retain_namespace (bool): If True, retains the namespace of tools in the current registry.
                If False, removes the namespace from tools after spinning off.

        Returns:
            ToolRegistry: A new registry containing the spun-off tools.

        Raises:
            ValueError: If no tools with the specified prefix are found.

        Notes:
            When `retain_namespace` is False, the `reduce_namespace` method is called
            to remove the namespace from tools in the current registry.
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
        new_registry._sub_registries.add(prefix)
        new_registry._tools = spun_off_tools  # Initialize with spun-off tools
        if not retain_namespace:
            new_registry.reduce_namespace()  # Optimize namespace removal using reduce_namespace

        # Remove the spun-off tools from the current registry
        self._tools = {
            name: tool
            for name, tool in self._tools.items()
            if not name.startswith(f"{prefix}.")
        }

        # Remove the prefix from sub-registries if it exists
        self._sub_registries.discard(prefix)

        # Optionally discard namespace if retain_namespace is False
        if not retain_namespace:
            self.reduce_namespace()

        return new_registry

    def register_from_mcp(
        self,
        server_url: str,
        with_namespace: Union[bool, str] = False,
    ):
        """Register all tools from an MCP server (synchronous entry point).

        Requires the [mcp] extra to be installed.

        Args:
            server_url (str): URL of the MCP server.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [mcp] extra is not installed.
        """
        try:
            from .mcp_integration import MCPIntegration

            mcp = MCPIntegration(self)
            return mcp.register_mcp_tools(server_url, with_namespace)
        except ImportError:
            raise ImportError(
                "MCP integration requires the [mcp] extra. "
                "Install with: pip install toolregistry[mcp]"
            )

    async def register_from_mcp_async(
        self,
        server_url: str,
        with_namespace: Union[bool, str] = False,
    ):
        """Async implementation to register all tools from an MCP server.

        Requires the [mcp] extra to be installed.

        Args:
            server_url (str): URL of the MCP server.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [mcp] extra is not installed.
        """
        try:
            from .mcp_integration import MCPIntegration

            mcp = MCPIntegration(self)
            return await mcp.register_mcp_tools_async(server_url, with_namespace)
        except ImportError:
            raise ImportError(
                "MCP integration requires the [mcp] extra. "
                "Install with: pip install toolregistry[mcp]"
            )

    def register_from_openapi(
        self,
        spec_url: str,
        base_url: Optional[str] = None,
        with_namespace: Union[bool, str] = False,
    ):
        """Register all tools from an OpenAPI specification (synchronous entry point).

        Requires the [openapi] extra to be installed.

        Args:
            spec_url (str): URL or path to the OpenAPI specification.
            base_url (Optional[str]): Optional base URL to use if the spec does not provide a server.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [openapi] extra is not installed.
        """
        try:
            from .openapi_integration import OpenAPIIntegration

            openapi = OpenAPIIntegration(self)
            return openapi.register_openapi_tools(spec_url, base_url, with_namespace)
        except ImportError:
            raise ImportError(
                "OpenAPI integration requires the [openapi] extra. "
                "Install with: pip install toolregistry[openapi]"
            )

    async def register_from_openapi_async(
        self,
        spec_url: str,
        base_url: Optional[str] = None,
        with_namespace: Union[bool, str] = False,
    ):
        """Async implementation to register all tools from an OpenAPI specification.

        Requires the [openapi] extra to be installed.

        Args:
            spec_url (str): URL or path to the OpenAPI specification.
            base_url (Optional[str]): Optional base URL to use if the spec does not provide a server.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [openapi] extra is not installed.
        """
        try:
            from .openapi_integration import OpenAPIIntegration

            openapi = OpenAPIIntegration(self)
            return await openapi.register_openapi_tools_async(
                spec_url, base_url, with_namespace
            )
        except ImportError:
            raise ImportError(
                "OpenAPI integration requires the [openapi] extra. "
                "Install with: pip install toolregistry[openapi]"
            )

    def register_from_class(
        self, cls: Union[Type, object], with_namespace: Union[bool, str] = False
    ):
        """Register all static methods from a class or instance as tools.

        Args:
            cls (Union[Type, object]): The class or instance containing static methods to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Example:
            >>> from toolregistry.hub import Calculator
            >>> registry = ToolRegistry()
            >>> registry.register_from_class(Calculator)

        Note:
            This method is now a convenience wrapper around the register() method's
            static method handling capability.
        """
        from .class_tool_integration import ClassToolIntegration

        hub = ClassToolIntegration(self)
        return hub.register_class_methods(cls, with_namespace)

    async def register_from_class_async(
        self, cls: Union[Type, object], with_namespace: Union[bool, str] = False
    ):
        """Async implementation to register all static methods from a class or instance as tools.

        Args:
            cls (Union[Type, object]): The class or instance containing static methods to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Example:
            >>> from toolregistry.hub import Calculator
            >>> registry = ToolRegistry()
            >>> registry.register_from_class(Calculator)
        """
        from .class_tool_integration import ClassToolIntegration

        hub = ClassToolIntegration(self)
        return await hub.register_class_methods_async(cls, with_namespace)

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

    # deprecated alias for backward compatibility
    @deprecated(reason="use register_from_mcp instead", version="0.4.4")
    def register_mcp_tools(
        self,
        server_url: str,
        with_namespace: Union[bool, str] = False,
    ):
        return self.register_from_mcp(server_url, with_namespace)

    @deprecated(reason="use register_from_mcp_async instead", version="0.4.4")
    async def register_mcp_tools_async(
        self,
        server_url: str,
        with_namespace: Union[bool, str] = False,
    ):
        return await self.register_from_mcp_async(server_url, with_namespace)

    @deprecated(reason="use register_from_openapi instead", version="0.4.4")
    def register_openapi_tools(
        self,
        spec_url: str,
        base_url: Optional[str] = None,
        with_namespace: Union[bool, str] = False,
    ):
        return self.register_from_openapi(spec_url, base_url, with_namespace)

    @deprecated(reason="use register_from_openapi_async instead", version="0.4.4")
    async def register_openapi_tools_async(
        self,
        spec_url: str,
        base_url: Optional[str] = None,
        with_namespace: Union[bool, str] = False,
    ):
        return await self.register_from_openapi_async(
            spec_url, base_url, with_namespace
        )

    @deprecated(reason="use register_from_class instead", version="0.4.4")
    def register_static_tools(
        self, cls: Type, with_namespace: Union[bool, str] = False
    ):
        return self.register_from_class(cls, with_namespace)

    @deprecated(reason="use register_from_class_async instead", version="0.4.4")
    async def register_static_tools_async(
        self, cls: Type, with_namespace: Union[bool, str] = False
    ):
        return await self.register_from_class_async(cls, with_namespace)
