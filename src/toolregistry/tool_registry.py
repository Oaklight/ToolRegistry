import json
import random
import string
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Type, Union

import httpx
from pydantic import AnyUrl

from .tool import Tool
from .utils import ChatCompletionMessageToolCall, normalize_tool_name

try:
    from fastmcp import FastMCP  # type: ignore
    from fastmcp.client.transports import ClientTransport  # type: ignore
except ImportError:
    pass

try:
    from langchain_core.tools import BaseTool as LCBaseTool  # type: ignore
except ImportError:
    pass
from .executor import Executor


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
        self._executor = Executor()

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
        transport: Union[
            "ClientTransport", "FastMCP", AnyUrl, Path, Dict[str, Any], str
        ],
        with_namespace: Union[bool, str] = False,
    ):
        """Register all tools from an MCP server (synchronous entry point).

        Requires the [mcp] extra to be installed.

        Args:
            transport (ClientTransport | FastMCP | AnyUrl | Path | Dict[str, Any] | str): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCP instance

        Examples:
            >>> # In-memory server
            >>> server = FastMCP(name="TestServer")
            >>> registry.register_from_mcp(server)

            >>> # SSE server URL
            >>> registry.register_from_mcp("http://localhost:8000/sse")

            >>> # WebSocket server URL
            >>> registry.register_from_mcp("ws://localhost:9000")

            >>> # Path to Python server script
            >>> registry.register_from_mcp("my_mcp_server.py")
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [mcp] extra is not installed
        """
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(self)
        return mcp.register_mcp_tools(transport, with_namespace)

    async def register_from_mcp_async(
        self,
        transport: Union[
            "ClientTransport", "FastMCP", AnyUrl, Path, Dict[str, Any], str
        ],
        with_namespace: Union[bool, str] = False,
    ):
        """Async implementation to register all tools from an MCP server.

        Requires the [mcp] extra to be installed.

        Args:
            transport (ClientTransport | FastMCP | AnyUrl | Path | Dict[str, Any] | str): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Existing ClientTransport instance
                - FastMCP instance

        Examples:
            >>> # In-memory server
            >>> server = FastMCP(name="TestServer")
            >>> await registry.register_from_mcp_async(server)

            >>> # SSE server URL
            >>> await registry.register_from_mcp_async("http://localhost:8000/sse")

            >>> # WebSocket server URL
            >>> await registry.register_from_mcp_async("ws://localhost:9000")

            >>> # Path to Python server script
            >>> await registry.register_from_mcp_async("my_mcp_server.py")

            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [mcp] extra is not installed
        """
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(self)
        return await mcp.register_mcp_tools_async(transport, with_namespace)

    def register_from_openapi(
        self,
        client: httpx.AsyncClient,
        openapi_spec: Dict[str, Any],
        with_namespace: Union[bool, str] = False,
    ):
        """Registers tools from OpenAPI specification synchronously.

        Args:
            client (httpx.AsyncClient): The HTTP client instance.
            openapi_spec (Dict[str, Any]): Parsed OpenAPI specification dictionary.
            with_namespace (Union[bool, str]): Specifies namespace usage:
                - `False`: No namespace is applied.
                - `True`: Namespace is derived from OpenAPI info.title.
                - `str`: Use the provided string as namespace.
                Defaults to False.

        Returns:
            Any: Result of the OpenAPI tool registration process.
        """
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(self)
        return openapi.register_openapi_tools(client, openapi_spec, with_namespace)

    async def register_from_openapi_async(
        self,
        client: httpx.AsyncClient,
        openapi_spec: Dict[str, Any],
        with_namespace: Union[bool, str] = False,
    ):
        """Registers tools from OpenAPI specification asynchronously.

        Args:
            client (httpx.AsyncClient): The HTTP client instance.
            openapi_spec (Dict[str, Any]): Parsed OpenAPI specification dictionary.
            with_namespace (Union[bool, str]): Specifies namespace usage:
                - `False`: No namespace is applied.
                - `True`: Namespace is derived from OpenAPI info.title.
                - `str`: Use the provided string as namespace.
                Defaults to False.

        Returns:
            Any: Result of the OpenAPI tool registration process.
        """
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(self)
        return await openapi.register_openapi_tools_async(
            client, openapi_spec, with_namespace
        )

    def register_from_langchain(
        self,
        langchain_tool: "LCBaseTool",
        with_namespace: Union[bool, str] = False,
    ):
        """Register a LangChain tool in the registry.

        Requires the [langchain] extra to be installed.

        Args:
            langchain_tool (LCBaseTool): The LangChain tool to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the tool name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [langchain] extra is not installed
        """
        LangChainIntegration = _import_langchain_integration()
        langchain = LangChainIntegration(self)
        return langchain.register_langchain_tools(langchain_tool, with_namespace)

    async def register_from_langchain_async(
        self,
        langchain_tool: "LCBaseTool",
        with_namespace: Union[bool, str] = False,
    ):
        """Async implementation to register a LangChain tool in the registry.

        Requires the [langchain] extra to be installed.

        Args:
            langchain_tool (LCBaseTool): The LangChain tool to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the tool name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Raises:
            ImportError: If [langchain] extra is not installed
        """
        LangChainIntegration = _import_langchain_integration()
        langchain = LangChainIntegration(self)
        return await langchain.register_langchain_tools_async(
            langchain_tool, with_namespace
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
        from .native import ClassToolIntegration

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
        from .native import ClassToolIntegration

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

    def set_execution_mode(self, mode: Literal["thread", "process"]) -> None:
        """Set the execution mode for parallel tasks.

        Args:
            mode (Literal["thread", "process"]): The desired execution mode.

        Raises:
            ValueError: If an invalid mode is provided.
        """
        return self._executor.set_execution_mode(mode)

    def execute_tool_calls(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        execution_mode: Optional[Literal["process", "thread"]] = None,
    ) -> Dict[str, str]:
        """Execute tool calls with concurrency using dill for serialization.

        Args:
            tool_calls: List of tool calls to be executed.
            execution_mode: Execution mode to use; defaults to the Executor's current mode.

        Returns:
            Dict[str, str]: Dictionary mapping tool call IDs to their results.
        """
        return self._executor.execute_tool_calls(tool_calls, execution_mode)

    def recover_tool_call_assistant_message(
        self,
        tool_calls: List[ChatCompletionMessageToolCall],
        tool_responses: Dict[str, str],
    ) -> List[Dict[str, Any]]:
        """Construct assistant messages from tool call results.

        Creates a conversation history with:
            - Assistant tool call requests
            - Tool execution responses

        Args:
            tool_calls (List[ChatCompletionMessageToolCall]): List of tool call objects.
            tool_responses (Dict[str, str]): Dictionary of tool call IDs to results.

        Returns:
            List[Dict[str, Any]]: List of message dictionaries in conversation format.
        """
        messages = []
        for tool_call in tool_calls:
            # Always ensure there's at least a placeholder in tool_responses to avoid KeyError
            if tool_call.id not in tool_responses:
                tool_responses[tool_call.id] = (
                    "No result (possibly concurrency/dill serialization error)"
                )

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


def _import_openapi_integration():
    """Helper function to import the OpenAPI integration module.

    Raises:
        ImportError: If the [openapi] extra is not installed.

    Returns:
        OpenAPIIntegration: The imported OpenAPIIntegration class.
    """
    try:
        from .openapi import OpenAPIIntegration

        return OpenAPIIntegration
    except ImportError:
        raise ImportError(
            "OpenAPI integration requires the [openapi] extra. "
            "Install with: pip install toolregistry[openapi]"
        )


def _import_mcp_integration():
    """Helper function to import the MCP integration module.

    Raises:
        ImportError: If the [mcp] extra is not installed.

    Returns:
        MCPIntegration: The imported OpenAPIIntegration class.
    """
    try:
        from .mcp import MCPIntegration

        return MCPIntegration
    except ImportError:
        raise ImportError(
            "MCP integration requires the [mcp] extra. "
            "Install with: pip install toolregistry[mcp]"
        )


def _import_langchain_integration():
    """Helper function to import the LangChain integration module.

    Raises:
        ImportError: If the [langchain] extra is not installed.

    Returns:
        LangChainIntegration: The imported LangChainIntegration class.
    """
    try:
        from .langchain import LangChainIntegration

        return LangChainIntegration
    except ImportError:
        raise ImportError(
            "LangChain integration requires the [langchain] extra. "
            "Install with: pip install toolregistry[langchain]"
        )
