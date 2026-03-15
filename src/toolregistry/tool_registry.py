import json
import logging
import random
import string
import threading
from pathlib import Path
from typing import Any, Literal
from collections.abc import Callable

from .events import ChangeCallback, ChangeEvent, ChangeEventType
from .executor import Executor
from .tool import Tool
from .types import (
    API_FORMATS,
    AnyToolCall,
    convert_tool_calls,
    recover_assistant_message,
    recover_tool_message,
)
from .utils import HttpxClientConfig, normalize_tool_name

logger = logging.getLogger(__name__)

try:
    from langchain_core.tools import BaseTool as LCBaseTool
except ImportError:
    pass


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

    # ============== dunder methods ==============
    def __init__(self, name: str | None = None) -> None:
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
        self._tools: dict[str, Tool] = {}
        self._sub_registries: set[str] = set()
        self._disabled: dict[str, str] = {}
        self._executor = Executor()
        self._change_callbacks: list[ChangeCallback] = []
        self._callback_lock = threading.Lock()

    def __contains__(self, name: str) -> bool:
        """Check if a tool with the given name is registered.

        Args:
            name (str): Name of the tool to check.

        Returns:
            bool: True if tool is registered, False otherwise.
        """
        return name in self._tools

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

    def __getitem__(self, key: str) -> Callable[..., Any] | None:
        """Enable key-value access to retrieve callables.

        Args:
            key (str): Name of the function.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        return self.get_callable(key)

    # ============== Execution ==============
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
        tool_calls: list[AnyToolCall],
        execution_mode: Literal["process", "thread"] | None = None,
    ) -> dict[str, str]:
        """Execute tool calls with concurrency using dill for serialization.

        Disabled tools are rejected with an error message instead of being
        executed.

        Args:
            tool_calls: List of tool calls to be executed in any supported format.
            execution_mode: Execution mode to use; defaults to the Executor's current mode.

        Returns:
            Dict[str, str]: Dictionary mapping tool call IDs to their results.
        """
        generic_tool_calls = convert_tool_calls(tool_calls)

        # Separate enabled and disabled tool calls
        enabled_calls = []
        tool_responses: dict[str, str] = {}

        for tc in generic_tool_calls:
            if not self.is_enabled(tc.name):
                reason = self.get_disable_reason(tc.name) or "Tool is disabled"
                tool_responses[tc.id] = (
                    f"Error: Tool '{tc.name}' is disabled. Reason: {reason}"
                )
            else:
                enabled_calls.append(tc)

        # Execute only enabled tool calls
        if enabled_calls:
            executed_responses = self._executor.execute_tool_calls(
                self.get_tool, enabled_calls, execution_mode
            )
            tool_responses.update(executed_responses)

        return tool_responses

    def recover_tool_call_assistant_message(
        self,
        tool_calls: list[AnyToolCall],
        tool_responses: dict[str, str],
        api_format: API_FORMATS = "openai-chatcompletion",
    ) -> list[dict[str, Any]]:
        """Construct assistant messages from tool call results.

        Creates a conversation history with:
            - Assistant tool call requests
            - Tool execution responses

        Args:
            tool_calls (List[AnyToolCall]): List of tool call objects in various formats.
            tool_responses (Dict[str, str]): Dictionary of tool call IDs to results.
            api_format (API_FORMATS): The desired API format for the output.

        Returns:
            List[Dict[str, Any]]: List of message dictionaries in conversation format.
        """
        messages = []
        generic_tool_calls = convert_tool_calls(tool_calls)

        # extend assistant message(s) of tool calls
        messages.extend(
            recover_assistant_message(generic_tool_calls, api_format=api_format)
        )
        # extend messages with tool responses
        messages.extend(recover_tool_message(tool_responses, api_format=api_format))
        return messages

    # ============== Namespace ==============

    def _update_sub_registries(self) -> None:
        """
        Update the internal set of sub-registries based on the registered tools.

        This method identifies sub-registry prefixes by examining the ``namespace``
        field of each tool first.  If a tool does not have a ``namespace`` set, it
        falls back to parsing the tool name for a dot-separated prefix.

        Side Effects:
            Modifies the `_sub_registries` attribute with the latest prefixes.

        Returns:
            None
        """
        prefixes: set[str] = set()
        for tool in self._tools.values():
            if tool.namespace:
                prefixes.add(tool.namespace)
            elif "." in tool.name:
                prefixes.add(tool.name.split(".", 1)[0])
        self._sub_registries = prefixes

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
        new_tools: dict[str, Tool] = {}
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

    # ============== Enable/Disable ==============

    def disable(self, name: str, reason: str = "") -> None:
        """Disable a tool or namespace. Uses raw name (not normalized).

        Args:
            name: The tool name or namespace to disable.
            reason: Optional reason for disabling.
        """
        self._disabled[name] = reason
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.DISABLE,
                tool_name=name,
                reason=reason or None,
            )
        )

    def enable(self, name: str) -> None:
        """Re-enable a tool or namespace.

        Args:
            name: The tool name or namespace to re-enable.
        """
        self._disabled.pop(name, None)
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.ENABLE,
                tool_name=name,
            )
        )

    def is_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled (not disabled at method or group level).

        Args:
            tool_name: The tool name to check.

        Returns:
            True if the tool is enabled, False otherwise.
        """
        if tool_name in self._disabled:
            return False
        tool = self._tools.get(tool_name)
        if tool and tool.namespace and tool.namespace in self._disabled:
            return False
        return True

    def get_disable_reason(self, tool_name: str) -> str | None:
        """Get the reason a tool is disabled, or None if enabled.

        Method-level disable takes priority over group-level.

        Args:
            tool_name: The tool name to check.

        Returns:
            The disable reason string, or None if the tool is enabled.
        """
        if tool_name in self._disabled:
            return self._disabled[tool_name]
        tool = self._tools.get(tool_name)
        if tool and tool.namespace:
            return self._disabled.get(tool.namespace)
        return None

    # ============== Change Callbacks ==============

    def on_change(self, callback: ChangeCallback) -> None:
        """Register a callback to be notified of tool state changes.

        The callback will be invoked synchronously whenever a tool is
        registered, unregistered, enabled, or disabled.

        Args:
            callback: Function that accepts a ChangeEvent parameter.
                     Must not raise exceptions that should propagate.

        Note:
            - Callbacks are invoked in registration order.
            - The same callback can be registered multiple times.
            - Callbacks should be lightweight; heavy processing should
              be offloaded to a separate thread/task.

        Example:
            ```python
            def my_handler(event: ChangeEvent) -> None:
                print(f"{event.event_type}: {event.tool_name}")
            registry.on_change(my_handler)
            ```
        """
        with self._callback_lock:
            self._change_callbacks.append(callback)

    def remove_on_change(self, callback: ChangeCallback) -> bool:
        """Remove a previously registered callback.

        Args:
            callback: The exact callback function to remove.

        Returns:
            True if the callback was found and removed, False otherwise.

        Note:
            If the same callback was registered multiple times,
            only the first occurrence is removed.

        Example:
            ```python
            registry.remove_on_change(my_handler)  # True
            ```
        """
        with self._callback_lock:
            try:
                self._change_callbacks.remove(callback)
                return True
            except ValueError:
                return False

    def _emit_change(self, event: ChangeEvent) -> None:
        """Notify all registered callbacks of a change event.

        Callbacks are invoked synchronously in registration order.
        Exceptions in callbacks are logged but do not propagate.

        Args:
            event: The change event to emit.
        """
        # Copy callback list to allow modification during iteration
        with self._callback_lock:
            callbacks = self._change_callbacks.copy()

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                # Log but don't propagate - one bad callback shouldn't
                # break the entire notification chain
                logger.warning(f"Change callback {callback!r} raised exception: {e}")

    # ============== Registration Methods ==============
    def register(
        self,
        tool_or_func: Callable | Tool,
        description: str | None = None,
        name: str | None = None,
        namespace: str | None = None,
        method_name: str | None = None,
    ):
        """Register a tool, either as a function, Tool instance, or static method.

        Args:
            tool_or_func (Union[Callable, Tool]): The tool to register, either as a function, Tool instance, or static method.
            description (Optional[str]): Description for function tools. If not provided, the function's docstring will be used.
            name (Optional[str]): Custom name for the tool. If not provided, defaults to function name for functions or tool.name for Tool instances.
            namespace (Optional[str]): Namespace for the tool. For static methods, defaults to class name if not provided.
            method_name (Optional[str]): Original method name of the tool.
        """
        if namespace:
            self._sub_registries.add(normalize_tool_name(namespace))

        if isinstance(tool_or_func, Tool):
            tool_or_func.update_namespace(namespace, force=True)
            self._tools[tool_or_func.name] = tool_or_func
            registered_name = tool_or_func.name
        else:
            tool = Tool.from_function(
                tool_or_func,
                description=description,
                name=name,
                namespace=namespace,
                method_name=method_name,
            )
            self._tools[tool.name] = tool
            registered_name = tool.name

        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.REGISTER,
                tool_name=registered_name,
            )
        )

    def register_from_mcp(
        self,
        transport: str | dict[str, Any] | Path,
        with_namespace: bool | str = False,
    ):
        """Register all tools from an MCP server (synchronous entry point).

        Requires the [mcp] extra to be installed.

        Args:
            transport (Union[str, Dict[str, Any], Path]): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Dict with "command", "args", "env" keys for stdio transport
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the server info name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Examples:
            ```python
            # SSE server URL
            registry.register_from_mcp("http://localhost:8000/sse")

            # WebSocket server URL
            registry.register_from_mcp("ws://localhost:9000")

            # Path to Python server script
            registry.register_from_mcp("my_mcp_server.py")
            ```

        Raises:
            ImportError: If [mcp] extra is not installed
        """
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(self)
        return mcp.register_mcp_tools(transport, with_namespace)

    async def register_from_mcp_async(
        self,
        transport: str | dict[str, Any] | Path,
        with_namespace: bool | str = False,
    ):
        """Async implementation to register all tools from an MCP server.

        Requires the [mcp] extra to be installed.

        Args:
            transport (Union[str, Dict[str, Any], Path]): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Dict with "command", "args", "env" keys for stdio transport
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the server info name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Examples:
            ```python
            # SSE server URL
            await registry.register_from_mcp_async("http://localhost:8000/sse")

            # WebSocket server URL
            await registry.register_from_mcp_async("ws://localhost:9000")

            # Path to Python server script
            await registry.register_from_mcp_async("my_mcp_server.py")
            ```

        Raises:
            ImportError: If [mcp] extra is not installed
        """
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(self)
        return await mcp.register_mcp_tools_async(transport, with_namespace)

    def register_from_openapi(
        self,
        client: HttpxClientConfig,
        openapi_spec: dict[str, Any],
        with_namespace: bool | str = False,
    ):
        """Registers tools from OpenAPI specification synchronously.

        Args:
            client (HttpxClientConfig): The httpx client config instance.
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
        client: HttpxClientConfig,
        openapi_spec: dict[str, Any],
        with_namespace: bool | str = False,
    ):
        """Registers tools from OpenAPI specification asynchronously.

        Args:
            client (HttpxClientConfig): The httpx client config instance.
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
        with_namespace: bool | str = False,
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
        with_namespace: bool | str = False,
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
        self,
        cls: type | object,
        with_namespace: bool | str = False,
        traverse_mro: bool = True,
    ):
        """Register all static methods from a class or instance as tools.

        Args:
            cls (Union[Type, object]): The class or instance containing static methods to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            traverse_mro (bool): Whether to traverse the MRO (Method Resolution
                Order) to include inherited methods. When True (default),
                methods from parent classes are also included (excluding
                ``object``), with subclass methods taking priority over parent
                class methods. When False, only methods defined directly on the
                class are registered.

        Example:
            ```python
            from toolregistry.hub import Calculator
            registry = ToolRegistry()
            registry.register_from_class(Calculator)
            ```

        Note:
            This method is now a convenience wrapper around the register() method's
            static method handling capability.
        """
        from .native import ClassToolIntegration

        hub = ClassToolIntegration(self, traverse_mro=traverse_mro)
        return hub.register_class_methods(cls, with_namespace)

    async def register_from_class_async(
        self,
        cls: type | object,
        with_namespace: bool | str = False,
        traverse_mro: bool = True,
    ):
        """Async implementation to register all static methods from a class or instance as tools.

        Args:
            cls (Union[Type, object]): The class or instance containing static methods to register.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the class name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            traverse_mro (bool): Whether to traverse the MRO (Method Resolution
                Order) to include inherited methods. When True (default),
                methods from parent classes are also included (excluding
                ``object``), with subclass methods taking priority over parent
                class methods. When False, only methods defined directly on the
                class are registered.

        Example:
            ```python
            from toolregistry.hub import Calculator
            registry = ToolRegistry()
            registry.register_from_class(Calculator)
            ```
        """
        from .native import ClassToolIntegration

        hub = ClassToolIntegration(self, traverse_mro=traverse_mro)
        return await hub.register_class_methods_async(cls, with_namespace)

    # ============== Presentation ==============
    def list_tools(self) -> list[str]:
        """List enabled tools only.

        Returns:
            List[str]: A list of enabled tool names.
        """
        return [n for n in self._tools if self.is_enabled(n)]

    get_available_tools = list_tools  # Alias for backward compatibility

    def list_all_tools(self) -> list[str]:
        """List all tools including disabled (for admin panel).

        Returns:
            List[str]: A list of all tool names.
        """
        return list(self._tools.keys())

    def get_tools_status(self) -> list[dict[str, Any]]:
        """Get status information for all registered tools.

        Returns a list of dictionaries containing status information for each tool,
        including whether it's enabled/disabled and the reason if disabled.

        Returns:
            list[dict[str, Any]]: List of tool status dictionaries, each containing:
                - name (str): Tool name (with namespace prefix if applicable)
                - enabled (bool): Whether the tool is currently enabled
                - reason (str | None): Reason for disabling, if disabled
                - namespace (str | None): Namespace the tool belongs to, if any

        Example:
            >>> registry = ToolRegistry()
            >>> registry.register(my_tool)
            >>> registry.disable("my_tool", reason="Under maintenance")
            >>> registry.get_tools_status()
            [
                {
                    "name": "my_tool",
                    "enabled": False,
                    "reason": "Under maintenance",
                    "namespace": None
                }
            ]
        """
        status_list: list[dict[str, Any]] = []
        for tool_name, tool in self._tools.items():
            enabled = self.is_enabled(tool_name)
            reason = self.get_disable_reason(tool_name) if not enabled else None
            status_list.append(
                {
                    "name": tool_name,
                    "enabled": enabled,
                    "reason": reason,
                    "namespace": tool.namespace,
                }
            )
        return status_list

    def get_tools_json(
        self,
        tool_name: str | None = None,
        *,
        api_format: API_FORMATS = "openai",
    ) -> list[dict[str, Any]]:
        """Get the JSON representation of registered tools, following JSON Schema.

        When no specific tool_name is given, only enabled tools are returned.

        Args:
            tool_name (Optional[str]): Optional name of specific tool to get schema for.
            api_format (Literal): Optional mode for formatting the schema.
                - 'openai-chatcompletion': Legacy format with is_async
                - 'openai-response': OpenAI function calling format

        Returns:
            List[Dict[str, Any]]: A list of tools in JSON format, compliant with JSON Schema.
        """
        if tool_name:
            target_tool = self.get_tool(tool_name)
            tools = [target_tool] if target_tool else []
        else:
            # Only return enabled tools
            tools = [t for t in self._tools.values() if self.is_enabled(t.name)]

        return [tool.get_json_schema(api_format) for tool in tools]

    def get_tool(self, tool_name: str) -> Tool | None:
        """Get a tool by its name.

        Args:
            tool_name (str): Name of the tool to retrieve.

        Returns:
            Optional[Tool]: The tool, or None if not found.
        """
        tool = self._tools.get(tool_name)
        return tool

    def get_callable(self, tool_name: str) -> Callable[..., Any] | None:
        """Get a callable function by its name.

        Args:
            tool_name (str): Name of the function to retrieve.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        tool = self.get_tool(tool_name)
        return tool.callable if tool else None


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
