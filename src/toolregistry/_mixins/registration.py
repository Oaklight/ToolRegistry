"""Registration mixin for ToolRegistry."""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable

from ..events import ChangeEvent, ChangeEventType, RefreshResult
from ..tool import Tool
from ..utils import HttpClientConfig, normalize_tool_name

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry


try:
    from langchain_core.tools import BaseTool as LCBaseTool
except ImportError:
    pass

_MISSING = object()


def _detect_source(target: Any) -> str:
    """Auto-detect the registration source from *target*'s type.

    Returns:
        A source string: ``"native"``, ``"class"``, or ``"langchain"``.

    Raises:
        TypeError: When the type is ambiguous (str, dict, Path) and the
            caller must pass ``source=`` explicitly.
    """
    if isinstance(target, Tool):
        return "native"
    if isinstance(target, type):
        return "class"
    try:
        from langchain_core.tools import BaseTool as _LCBase

        if isinstance(target, _LCBase):
            return "langchain"
    except ImportError:
        pass
    if callable(target):
        return "native"
    if not isinstance(target, (str, dict, Path)):
        return "class"
    raise TypeError(
        f"Cannot auto-detect registration source for {type(target).__name__!r}. "
        f"Pass source='mcp' or source='openapi' explicitly."
    )


class RegistrationMixin:
    """Mixin providing tool registration methods."""

    # Type stubs for attributes/methods from other mixins
    _tools: dict[str, Tool]
    _sub_registries: set[str]
    _disabled: dict[str, str]  # Owned by EnableDisableMixin

    if TYPE_CHECKING:

        def _emit_change(self, event: ChangeEvent) -> None: ...

        def _run_post_register_hooks(self, tool_name: str, tool: Tool) -> None: ...

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mcp_integrations: list = []
        self._openapi_integrations: list = []

    # ------------------------------------------------------------------ #
    #  Unified public API                                                 #
    # ------------------------------------------------------------------ #

    def register(
        self,
        target: Callable | Tool | type | object = _MISSING,  # type: ignore[assignment]
        *,
        source: str | None = None,
        namespace: bool | str | None = None,
        description: str | None = None,
        name: str | None = None,
        method_name: str | None = None,
        **kwargs: Any,
    ):
        """Register a tool from any supported source.

        When *source* is ``None`` the source type is auto-detected from
        *target*:

        * ``Tool`` instance or callable → native registration
        * ``type`` → class registration (methods become tools)
        * LangChain ``BaseTool`` instance → LangChain integration
        * Other object instances → class registration (instance methods)
        * ``str``, ``dict``, ``Path`` → **cannot** be auto-detected; pass
          ``source='mcp'`` or ``source='openapi'`` explicitly.

        Args:
            target: The thing to register — a function, ``Tool``, class,
                instance, LangChain tool, MCP transport, or
                ``HttpClientConfig`` (for OpenAPI).
            source: Explicit source hint.  One of ``"native"``,
                ``"class"``, ``"mcp"``, ``"openapi"``, ``"langchain"``,
                or ``None`` for auto-detection.
            namespace: Namespace for the registered tools.
                ``None``/``False`` → no namespace.
                ``True`` → derive from the source.
                A string → use that string as the namespace.
            description: Description override (native source only).
            name: Name override (native source only).
            method_name: Original method name (native source only).
            **kwargs: Additional keyword arguments forwarded to the
                underlying integration (e.g. ``persistent``, ``headers``,
                ``traverse_mro``, ``constructor_kwargs``, ``openapi_spec``,
                ``spec_url``).

        Raises:
            TypeError: If *target* is missing, or its type cannot be
                auto-detected and *source* is not given.
            ValueError: If *source* is not a recognised value.

        Examples:
            >>> registry.register(my_func)
            >>> registry.register(MyClass, source="class", namespace="math")
            >>> registry.register("http://localhost:8000", source="mcp")
        """
        if target is _MISSING:
            raise TypeError("register() missing required argument: 'target'")

        resolved = source or _detect_source(target)
        ns = _normalise_namespace(namespace)

        if resolved == "native":
            self._register_native(
                target,
                description=description,
                name=name,
                namespace=ns,
                method_name=method_name,
            )
        elif resolved == "class":
            self._register_class(target, namespace=ns, **kwargs)
        elif resolved == "mcp":
            self._register_mcp(target, namespace=ns, **kwargs)
        elif resolved == "openapi":
            self._register_openapi(target, namespace=ns, **kwargs)
        elif resolved == "langchain":
            self._register_langchain(target, namespace=ns, **kwargs)
        else:
            raise ValueError(
                f"Unknown source: {resolved!r}. Supported values: "
                "'native', 'class', 'mcp', 'openapi', 'langchain'."
            )

    async def register_async(
        self,
        target: Callable | Tool | type | object = _MISSING,  # type: ignore[assignment]
        *,
        source: str | None = None,
        namespace: bool | str | None = None,
        description: str | None = None,
        name: str | None = None,
        method_name: str | None = None,
        **kwargs: Any,
    ):
        """Async version of :meth:`register`.

        See :meth:`register` for full documentation.
        """
        if target is _MISSING:
            raise TypeError("register_async() missing required argument: 'target'")

        resolved = source or _detect_source(target)
        ns = _normalise_namespace(namespace)

        if resolved == "native":
            self._register_native(
                target,
                description=description,
                name=name,
                namespace=ns,
                method_name=method_name,
            )
        elif resolved == "class":
            await self._register_class_async(target, namespace=ns, **kwargs)
        elif resolved == "mcp":
            await self._register_mcp_async(target, namespace=ns, **kwargs)
        elif resolved == "openapi":
            await self._register_openapi_async(target, namespace=ns, **kwargs)
        elif resolved == "langchain":
            await self._register_langchain_async(target, namespace=ns, **kwargs)
        else:
            raise ValueError(
                f"Unknown source: {resolved!r}. Supported values: "
                "'native', 'class', 'mcp', 'openapi', 'langchain'."
            )

    # ------------------------------------------------------------------ #
    #  Private dispatch methods                                           #
    # ------------------------------------------------------------------ #

    def _register_native(
        self,
        tool_or_func: Callable | Tool | Any,
        description: str | None = None,
        name: str | None = None,
        namespace: bool | str | None = None,
        method_name: str | None = None,
    ):
        """Register a single function or ``Tool`` instance."""
        ns_str: str | None = namespace if isinstance(namespace, str) else None
        if ns_str:
            self._sub_registries.add(normalize_tool_name(ns_str))

        sep = getattr(self, "_name_sep", "-")

        if isinstance(tool_or_func, Tool):
            tool_or_func.update_namespace(ns_str, force=True, sep=sep)
            self._tools[tool_or_func.name] = tool_or_func
            registered_name = tool_or_func.name
            registered_tool = tool_or_func
        else:
            tool = Tool.from_function(
                tool_or_func,
                description=description,
                name=name,
                namespace=ns_str,
                method_name=method_name,
            )
            self._tools[tool.name] = tool
            registered_name = tool.name
            registered_tool = tool

        self._run_post_register_hooks(registered_name, registered_tool)

        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.REGISTER,
                tool_name=registered_name,
            )
        )

    def _unregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Args:
            name: The registered name of the tool to remove.

        Returns:
            True if the tool was found and removed, False otherwise.
        """
        tool = self._tools.pop(name, None)
        if tool is None:
            return False
        self._disabled.pop(name, None)
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.UNREGISTER,
                tool_name=name,
            )
        )
        return True

    def _register_class(self, cls_or_instance, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        traverse_mro = kwargs.pop("traverse_mro", True)
        constructor_kwargs = kwargs.pop("constructor_kwargs", None)
        from ..integrations.native import ClassToolIntegration

        hub = ClassToolIntegration(
            cast("ToolRegistry", self), traverse_mro=traverse_mro
        )
        return hub.register_class_methods(
            cls_or_instance, namespace, constructor_kwargs
        )

    async def _register_class_async(self, cls_or_instance, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        traverse_mro = kwargs.pop("traverse_mro", True)
        constructor_kwargs = kwargs.pop("constructor_kwargs", None)
        from ..integrations.native import ClassToolIntegration

        hub = ClassToolIntegration(
            cast("ToolRegistry", self), traverse_mro=traverse_mro
        )
        return await hub.register_class_methods_async(
            cls_or_instance, namespace, constructor_kwargs
        )

    def _register_mcp(self, transport, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        persistent = kwargs.pop("persistent", True)
        headers = kwargs.pop("headers", None)
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(cast("ToolRegistry", self))
        mcp.register_mcp_tools(transport, namespace, persistent, headers=headers)
        self._mcp_integrations.append(mcp)

    async def _register_mcp_async(self, transport, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        persistent = kwargs.pop("persistent", True)
        headers = kwargs.pop("headers", None)
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(cast("ToolRegistry", self))
        await mcp.register_mcp_tools_async(
            transport, namespace, persistent, headers=headers
        )
        self._mcp_integrations.append(mcp)

    def _register_openapi(self, client, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        openapi_spec = kwargs.pop("openapi_spec", None)
        if openapi_spec is None:
            raise TypeError(
                "register() with source='openapi' requires an "
                "openapi_spec=... keyword argument."
            )
        persistent = kwargs.pop("persistent", True)
        spec_url = kwargs.pop("spec_url", None)
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(cast("ToolRegistry", self))
        openapi.register_openapi_tools(
            client, openapi_spec, namespace, persistent, spec_url=spec_url
        )
        self._openapi_integrations.append(openapi)

    async def _register_openapi_async(self, client, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        openapi_spec = kwargs.pop("openapi_spec", None)
        if openapi_spec is None:
            raise TypeError(
                "register_async() with source='openapi' requires an "
                "openapi_spec=... keyword argument."
            )
        persistent = kwargs.pop("persistent", True)
        spec_url = kwargs.pop("spec_url", None)
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(cast("ToolRegistry", self))
        await openapi.register_openapi_tools_async(
            client, openapi_spec, namespace, persistent, spec_url=spec_url
        )
        self._openapi_integrations.append(openapi)

    def _register_langchain(self, langchain_tool, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        LangChainIntegration = _import_langchain_integration()
        langchain = LangChainIntegration(cast("ToolRegistry", self))
        return langchain.register_langchain_tools(langchain_tool, namespace)

    async def _register_langchain_async(self, langchain_tool, *, namespace, **kwargs):
        namespace = _resolve_namespace_compat(namespace, kwargs)
        LangChainIntegration = _import_langchain_integration()
        langchain = LangChainIntegration(cast("ToolRegistry", self))
        return await langchain.register_langchain_tools_async(langchain_tool, namespace)

    # ------------------------------------------------------------------ #
    #  Deprecated aliases                                                 #
    # ------------------------------------------------------------------ #

    def register_from_mcp(
        self,
        transport: str | dict[str, Any] | Path,
        namespace: bool | str = False,
        persistent: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        """Deprecated: use ``register(transport, source='mcp')`` instead."""
        warnings.warn(
            "register_from_mcp() is deprecated, use "
            "register(transport, source='mcp', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.register(
            transport,
            source="mcp",
            namespace=namespace,
            persistent=persistent,
            headers=headers,
            **kwargs,
        )

    async def register_from_mcp_async(
        self,
        transport: str | dict[str, Any] | Path,
        namespace: bool | str = False,
        persistent: bool = True,
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        """Deprecated: use ``register_async(transport, source='mcp')`` instead."""
        warnings.warn(
            "register_from_mcp_async() is deprecated, use "
            "register_async(transport, source='mcp', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        await self.register_async(
            transport,
            source="mcp",
            namespace=namespace,
            persistent=persistent,
            headers=headers,
            **kwargs,
        )

    def register_from_openapi(
        self,
        client: HttpClientConfig,
        openapi_spec: dict[str, Any],
        namespace: bool | str = False,
        persistent: bool = True,
        spec_url: str | None = None,
        **kwargs,
    ):
        """Deprecated: use ``register(client, source='openapi', openapi_spec=...)`` instead."""
        warnings.warn(
            "register_from_openapi() is deprecated, use "
            "register(client, source='openapi', openapi_spec=...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.register(
            client,
            source="openapi",
            namespace=namespace,
            openapi_spec=openapi_spec,
            persistent=persistent,
            spec_url=spec_url,
            **kwargs,
        )

    async def register_from_openapi_async(
        self,
        client: HttpClientConfig,
        openapi_spec: dict[str, Any],
        namespace: bool | str = False,
        persistent: bool = True,
        spec_url: str | None = None,
        **kwargs,
    ):
        """Deprecated: use ``register_async(client, source='openapi', openapi_spec=...)`` instead."""
        warnings.warn(
            "register_from_openapi_async() is deprecated, use "
            "register_async(client, source='openapi', openapi_spec=...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        await self.register_async(
            client,
            source="openapi",
            namespace=namespace,
            openapi_spec=openapi_spec,
            persistent=persistent,
            spec_url=spec_url,
            **kwargs,
        )

    def register_from_langchain(
        self,
        langchain_tool: LCBaseTool,
        namespace: bool | str = False,
        **kwargs,
    ):
        """Deprecated: use ``register(langchain_tool, source='langchain')`` instead."""
        warnings.warn(
            "register_from_langchain() is deprecated, use "
            "register(langchain_tool, source='langchain', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.register(
            langchain_tool,
            source="langchain",
            namespace=namespace,
            **kwargs,
        )

    async def register_from_langchain_async(
        self,
        langchain_tool: LCBaseTool,
        namespace: bool | str = False,
        **kwargs,
    ):
        """Deprecated: use ``register_async(langchain_tool, source='langchain')`` instead."""
        warnings.warn(
            "register_from_langchain_async() is deprecated, use "
            "register_async(langchain_tool, source='langchain', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        await self.register_async(
            langchain_tool,
            source="langchain",
            namespace=namespace,
            **kwargs,
        )

    def register_from_class(
        self,
        cls: type | object,
        namespace: bool | str = False,
        traverse_mro: bool = True,
        constructor_kwargs: dict | None = None,
        **kwargs,
    ):
        """Deprecated: use ``register(cls, source='class')`` instead."""
        warnings.warn(
            "register_from_class() is deprecated, use "
            "register(cls, source='class', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.register(
            cls,
            source="class",
            namespace=namespace,
            traverse_mro=traverse_mro,
            constructor_kwargs=constructor_kwargs,
            **kwargs,
        )

    async def register_from_class_async(
        self,
        cls: type | object,
        namespace: bool | str = False,
        traverse_mro: bool = True,
        constructor_kwargs: dict | None = None,
        **kwargs,
    ):
        """Deprecated: use ``register_async(cls, source='class')`` instead."""
        warnings.warn(
            "register_from_class_async() is deprecated, use "
            "register_async(cls, source='class', ...) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        await self.register_async(
            cls,
            source="class",
            namespace=namespace,
            traverse_mro=traverse_mro,
            constructor_kwargs=constructor_kwargs,
            **kwargs,
        )

    # ---- Refresh ----

    def refresh_from_openapi(
        self,
        index: int = 0,
        *,
        openapi_spec: dict[str, Any] | None = None,
    ) -> RefreshResult:
        """Re-fetch the OpenAPI spec for an integration and update tools.

        Args:
            index: Index into the list of registered OpenAPI integrations
                (in the order they were registered).  Defaults to 0.
            openapi_spec: Optional pre-parsed spec dict.  When ``None``,
                the spec is re-fetched from the stored URL (with ETag).

        Returns:
            A :class:`RefreshResult` describing what changed.
        """
        if index >= len(self._openapi_integrations):
            raise IndexError(
                f"No OpenAPI integration at index {index} "
                f"({len(self._openapi_integrations)} registered)."
            )
        return self._openapi_integrations[index].refresh(openapi_spec)

    async def refresh_from_openapi_async(
        self,
        index: int = 0,
        *,
        openapi_spec: dict[str, Any] | None = None,
    ) -> RefreshResult:
        """Async version of :meth:`refresh_from_openapi`."""
        if index >= len(self._openapi_integrations):
            raise IndexError(
                f"No OpenAPI integration at index {index} "
                f"({len(self._openapi_integrations)} registered)."
            )
        return await self._openapi_integrations[index].refresh_async(openapi_spec)

    def refresh_from_mcp(self, index: int = 0) -> RefreshResult:
        """Re-list tools from an MCP server and update the registry.

        Args:
            index: Index into the list of registered MCP integrations
                (in the order they were registered).  Defaults to 0.

        Returns:
            A :class:`RefreshResult` describing what changed.
        """
        if index >= len(self._mcp_integrations):
            raise IndexError(
                f"No MCP integration at index {index} "
                f"({len(self._mcp_integrations)} registered)."
            )
        return self._mcp_integrations[index].refresh()

    async def refresh_from_mcp_async(self, index: int = 0) -> RefreshResult:
        """Async version of :meth:`refresh_from_mcp`."""
        if index >= len(self._mcp_integrations):
            raise IndexError(
                f"No MCP integration at index {index} "
                f"({len(self._mcp_integrations)} registered)."
            )
        return await self._mcp_integrations[index].refresh_async()

    def refresh_all(self) -> list[RefreshResult]:
        """Refresh all registered remote sources (OpenAPI and MCP).

        Returns:
            A list of :class:`RefreshResult`, one per integration.
        """
        results: list[RefreshResult] = []
        for integration in self._openapi_integrations:
            results.append(integration.refresh())
        for integration in self._mcp_integrations:
            results.append(integration.refresh())
        if results:
            self._emit_change(ChangeEvent(event_type=ChangeEventType.REFRESH_ALL))
        return results

    async def refresh_all_async(self) -> list[RefreshResult]:
        """Async version of :meth:`refresh_all`."""
        results: list[RefreshResult] = []
        for integration in self._openapi_integrations:
            results.append(await integration.refresh_async())
        for integration in self._mcp_integrations:
            results.append(await integration.refresh_async())
        if results:
            self._emit_change(ChangeEvent(event_type=ChangeEventType.REFRESH_ALL))
        return results


def _normalise_namespace(ns: bool | str | None) -> bool | str:
    """Map the unified namespace representation to the internal one."""
    if ns is None:
        return False
    return ns


def _resolve_namespace_compat(
    namespace: bool | str, kwargs: dict[str, Any]
) -> bool | str:
    """Handle deprecated ``with_namespace`` keyword argument.

    If the caller passed ``with_namespace=...`` via **kwargs, emit a
    deprecation warning and use that value instead of *namespace*.
    """
    if "with_namespace" in kwargs:
        warnings.warn(
            "with_namespace is deprecated, use namespace instead.",
            DeprecationWarning,
            stacklevel=3,
        )
        return kwargs.pop("with_namespace")
    return namespace


def _import_openapi_integration():
    try:
        from ..integrations.openapi import OpenAPIIntegration

        return OpenAPIIntegration
    except ImportError:
        raise ImportError(
            "OpenAPI integration requires the [openapi] extra. "
            "Install with: pip install toolregistry[openapi]"
        )


def _import_mcp_integration():
    try:
        from ..integrations.mcp import MCPIntegration

        return MCPIntegration
    except ImportError:
        raise ImportError(
            "MCP integration requires the [mcp] extra. "
            "Install with: pip install toolregistry[mcp]"
        )


def _import_langchain_integration():
    try:
        from ..integrations.langchain import LangChainIntegration

        return LangChainIntegration
    except ImportError:
        raise ImportError(
            "LangChain integration requires the [langchain] extra. "
            "Install with: pip install toolregistry[langchain]"
        )
