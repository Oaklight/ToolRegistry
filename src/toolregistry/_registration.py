"""Registration mixin for ToolRegistry."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable

from .events import ChangeEvent, ChangeEventType
from .tool import Tool
from .utils import HttpxClientConfig, normalize_tool_name

if TYPE_CHECKING:
    from .tool_registry import ToolRegistry


try:
    from langchain_core.tools import BaseTool as LCBaseTool
except ImportError:
    pass


class RegistrationMixin:
    """Mixin providing tool registration methods."""

    # Type stubs for attributes/methods from other mixins
    _tools: dict[str, Tool]
    _sub_registries: set[str]

    if TYPE_CHECKING:

        def _emit_change(self, event: ChangeEvent) -> None: ...

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mcp_integrations: list = []
        self._openapi_integrations: list = []

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
        persistent: bool = True,
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
            persistent (bool): If True (default), keep the connection open
                across tool calls. If False, create a new connection per call.

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
        mcp = MCPIntegration(cast("ToolRegistry", self))
        mcp.register_mcp_tools(transport, with_namespace, persistent)
        self._mcp_integrations.append(mcp)

    async def register_from_mcp_async(
        self,
        transport: str | dict[str, Any] | Path,
        with_namespace: bool | str = False,
        persistent: bool = True,
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
            persistent (bool): If True (default), keep the connection open
                across tool calls. If False, create a new connection per call.

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
        mcp = MCPIntegration(cast("ToolRegistry", self))
        await mcp.register_mcp_tools_async(transport, with_namespace, persistent)
        self._mcp_integrations.append(mcp)

    def register_from_openapi(
        self,
        client: HttpxClientConfig,
        openapi_spec: dict[str, Any],
        with_namespace: bool | str = False,
        persistent: bool = True,
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
            persistent (bool): If True (default), reuse a persistent HTTP
                client for connection pooling.

        Returns:
            Any: Result of the OpenAPI tool registration process.
        """
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(cast("ToolRegistry", self))
        openapi.register_openapi_tools(client, openapi_spec, with_namespace, persistent)
        self._openapi_integrations.append(openapi)

    async def register_from_openapi_async(
        self,
        client: HttpxClientConfig,
        openapi_spec: dict[str, Any],
        with_namespace: bool | str = False,
        persistent: bool = True,
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
            persistent (bool): If True (default), reuse a persistent HTTP
                client for connection pooling.

        Returns:
            Any: Result of the OpenAPI tool registration process.
        """
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(cast("ToolRegistry", self))
        await openapi.register_openapi_tools_async(
            client, openapi_spec, with_namespace, persistent
        )
        self._openapi_integrations.append(openapi)

    def register_from_langchain(
        self,
        langchain_tool: LCBaseTool,
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
        langchain = LangChainIntegration(cast("ToolRegistry", self))
        return langchain.register_langchain_tools(langchain_tool, with_namespace)

    async def register_from_langchain_async(
        self,
        langchain_tool: LCBaseTool,
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
        langchain = LangChainIntegration(cast("ToolRegistry", self))
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

        hub = ClassToolIntegration(
            cast("ToolRegistry", self), traverse_mro=traverse_mro
        )
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

        hub = ClassToolIntegration(
            cast("ToolRegistry", self), traverse_mro=traverse_mro
        )
        return await hub.register_class_methods_async(cls, with_namespace)


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
        MCPIntegration: The imported MCPIntegration class.
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
