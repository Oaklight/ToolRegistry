"""Registration mixin for ToolRegistry."""

from __future__ import annotations

import dataclasses
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Callable

from ..events import ChangeEvent, ChangeEventType, RefreshResult
from .._names import NameSeparator
from ..tool import Tool
from ..utils import HttpClientConfig, normalize_tool_name
from .._warnings import warn_at_user_frame

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
    if not isinstance(target, (str, dict, Path, int, float, bool, bytes, type(None))):
        return "class"
    raise TypeError(
        f"Cannot auto-detect registration source for {type(target).__name__!r}. "
        f"Pass source='mcp' or source='openapi' explicitly."
    )


def _validate_filter_kwargs(source: str, kwargs: dict[str, Any]) -> None:
    """Validate registration-time ``include`` / ``exclude`` arguments.

    Args:
        source: The resolved registration source.
        kwargs: Keyword arguments passed to ``register()`` /
            ``register_async()``.

    Raises:
        ValueError: If both ``include`` and ``exclude`` are given, or if a
            filter is passed to a source that does not support it.
    """
    include = kwargs.get("include")
    exclude = kwargs.get("exclude")
    if include is None and exclude is None:
        return
    if include is not None and exclude is not None:
        raise ValueError("include and exclude are mutually exclusive; pass only one.")
    if source not in ("mcp", "openapi", "langchain"):
        raise ValueError(
            f"include/exclude filters are not supported for source={source!r}; "
            "they apply to the 'mcp', 'openapi', and 'langchain' sources only."
        )


def _pop_filter_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Pop ``include`` / ``exclude`` from *kwargs*, dropping unset values.

    Only forwards a filter when the caller actually passed one, so the
    integration call signature is unchanged for the common unfiltered case.

    Args:
        kwargs: Keyword arguments forwarded to an integration dispatch method.

    Returns:
        A dict containing ``include`` and/or ``exclude``, possibly empty.
    """
    include = kwargs.pop("include", None)
    exclude = kwargs.pop("exclude", None)
    filter_kwargs: dict[str, Any] = {}
    if include is not None:
        filter_kwargs["include"] = include
    if exclude is not None:
        filter_kwargs["exclude"] = exclude
    return filter_kwargs


def _forward_allow_replace(allow_replace: bool) -> dict[str, bool]:
    """Return the ``allow_replace`` kwarg only when it is set.

    Keeping the default out of the forwarded call preserves the existing
    integration signatures for callers that do not opt in.

    Args:
        allow_replace: Whether the caller acknowledged replacement.

    Returns:
        ``{"allow_replace": True}`` when set, otherwise an empty dict.
    """
    return {"allow_replace": True} if allow_replace else {}


class RegistrationMixin:
    """Mixin providing tool registration methods."""

    # Type stubs for attributes/methods from other mixins
    _tools: dict[str, Tool]
    _sub_registries: set[str]
    _disabled: dict[str, str]  # Owned by EnableDisableMixin
    _overrides: dict[str, Tool]  # name -> displaced original tool
    name_sep: NameSeparator  # Provided by ToolRegistry

    if TYPE_CHECKING:

        def _emit_change(self, event: ChangeEvent) -> None: ...

        def _run_post_register_hooks(self, tool_name: str, tool: Tool) -> None: ...

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mcp_integrations: list = []
        self._openapi_integrations: list = []
        self._overrides: dict[str, Tool] = {}

    # ------------------------------------------------------------------ #
    #  Unified public API                                                 #
    # ------------------------------------------------------------------ #

    def register(
        self,
        target: Any = _MISSING,
        description: str | None = None,
        name: str | None = None,
        *,
        source: str | None = None,
        namespace: bool | str | None = None,
        method_name: str | None = None,
        allow_replace: bool = False,
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
            allow_replace: When ``True``, replace a tool already registered
                under the same name without warning.  When ``False``
                (default), the existing tool is still replaced, but a
                ``UserWarning`` is emitted and a
                :attr:`~toolregistry.events.ChangeEventType.REPLACE`
                change event is sent.  The previous definition is
                discarded either way; the flag only acknowledges that.
            **kwargs: Additional keyword arguments forwarded to the
                underlying integration (e.g. ``persistent``, ``headers``,
                ``traverse_mro``, ``constructor_kwargs``, ``openapi_spec``,
                ``spec_url``, ``include``, ``exclude``).
                ``include`` / ``exclude`` are accepted by the ``"mcp"``,
                ``"openapi"``, and ``"langchain"`` sources.  Each is a name,
                an ``fnmatch`` glob pattern, or a list of them, matched
                against the raw remote tool name (the MCP tool name or the
                OpenAPI ``operationId``), the post-namespace registered name
                (e.g. ``gh-list_issues``), and the snake_case form of each.
                A bare string is treated as a single pattern.  Matching is
                case-sensitive, and a normalized spelling can match more
                than one tool when two advertised names collide after
                normalization.  Only one of the two may be given.
                Filtered-out tools never reach the registry, so they stay
                invisible to discovery and the admin panel.  If a filter
                rejects every tool a source offers, a ``UserWarning`` is
                emitted.

        Raises:
            TypeError: If *target* is missing, or its type cannot be
                auto-detected and *source* is not given.
            ValueError: If *source* is not a recognised value, if both
                ``include`` and ``exclude`` are given, or if a filter is
                passed to a source that does not support it.

        Note:
            Callable instances (objects with ``__call__``) are registered
            as a single native tool.  To register all methods instead,
            pass ``source="class"`` explicitly.

            Repeated registration is only a replacement when the resulting
            ``Tool`` differs from the stored one.  Registering the same
            ``Tool`` object again — including with the same namespace, where
            namespace application makes a field-equal copy — emits neither a
            warning nor a ``REPLACE`` event.

        Examples:
            >>> registry.register(my_func)
            >>> registry.register(MyClass, source="class", namespace="math")
            >>> registry.register("http://localhost:8000", source="mcp")
        """
        target, resolved, ns = self._resolve_registration(
            target, source, namespace, "register", kwargs
        )

        if allow_replace:
            kwargs["allow_replace"] = True

        if resolved == "native":
            return self._register_native(
                target,
                description=description,
                name=name,
                namespace=ns,
                method_name=method_name,
                allow_replace=allow_replace,
            )
        elif resolved == "class":
            return self._register_class(target, namespace=ns, **kwargs)
        elif resolved == "mcp":
            return self._register_mcp(target, namespace=ns, **kwargs)
        elif resolved == "openapi":
            return self._register_openapi(target, namespace=ns, **kwargs)
        elif resolved == "langchain":
            return self._register_langchain(target, namespace=ns, **kwargs)
        else:
            raise ValueError(
                f"Unknown source: {resolved!r}. Supported values: "
                "'native', 'class', 'mcp', 'openapi', 'langchain'."
            )

    async def register_async(
        self,
        target: Any = _MISSING,
        description: str | None = None,
        name: str | None = None,
        *,
        source: str | None = None,
        namespace: bool | str | None = None,
        method_name: str | None = None,
        allow_replace: bool = False,
        **kwargs: Any,
    ):
        """Async version of :meth:`register`.

        See :meth:`register` for full documentation.
        """
        target, resolved, ns = self._resolve_registration(
            target, source, namespace, "register_async", kwargs
        )

        if allow_replace:
            kwargs["allow_replace"] = True

        if resolved == "native":
            return self._register_native(
                target,
                description=description,
                name=name,
                namespace=ns,
                method_name=method_name,
                allow_replace=allow_replace,
            )
        elif resolved == "class":
            return await self._register_class_async(target, namespace=ns, **kwargs)
        elif resolved == "mcp":
            return await self._register_mcp_async(target, namespace=ns, **kwargs)
        elif resolved == "openapi":
            return await self._register_openapi_async(target, namespace=ns, **kwargs)
        elif resolved == "langchain":
            return await self._register_langchain_async(target, namespace=ns, **kwargs)
        else:
            raise ValueError(
                f"Unknown source: {resolved!r}. Supported values: "
                "'native', 'class', 'mcp', 'openapi', 'langchain'."
            )

    def _resolve_registration(
        self,
        target: Any,
        source: str | None,
        namespace: bool | str | None,
        method_name: str,
        kwargs: dict[str, Any],
    ) -> tuple[Any, str, bool | str]:
        """Validate args and resolve source + namespace for register/register_async."""
        if target is _MISSING:
            raise TypeError(f"{method_name}() missing required argument: 'target'")
        resolved = source or _detect_source(target)
        ns = _resolve_namespace_compat(_normalise_namespace(namespace), kwargs)
        _validate_filter_kwargs(resolved, kwargs)
        return target, resolved, ns

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
        allow_replace: bool = False,
    ):
        """Register a single function or ``Tool`` instance.

        Args:
            tool_or_func: A ``Tool`` instance, callable, or class instance.
            description: Description override for a new ``Tool``.
            name: Name override for a new ``Tool``.
            namespace: Optional namespace prefix.
            method_name: Original method name, when registering a class
                method.
            allow_replace: Acknowledge replacing an existing tool under the
                same name without warning.
        """
        if namespace is True:
            raise ValueError(
                "namespace=True is not supported for native function "
                "registration; pass a string namespace instead."
            )
        ns_str: str | None = namespace if isinstance(namespace, str) else None
        if ns_str:
            self._sub_registries.add(normalize_tool_name(ns_str))

        sep = self.name_sep

        if isinstance(tool_or_func, Tool):
            tool_or_func = tool_or_func.update_namespace(ns_str, force=True, sep=sep)
            registered_tool = tool_or_func
        else:
            registered_tool = Tool.from_function(
                tool_or_func,
                description=description,
                name=name,
                namespace=ns_str,
                method_name=method_name,
                sep=sep,
            )
        registered_name = registered_tool.name

        existing = self._tools.get(registered_name)
        # Field equality, not identity: applying a namespace returns a
        # ``dataclasses.replace()`` copy, so re-registering the same ``Tool``
        # with the same namespace would otherwise look like a replacement.
        replaced = existing is not None and existing != registered_tool
        was_overridden = registered_name in self._overrides

        self._tools[registered_name] = registered_tool

        # A plain registration onto an overridden name supersedes the
        # override: the newly registered tool is now the current definition,
        # so the displaced record (and its restore path) no longer applies.
        self._overrides.pop(registered_name, None)

        self._run_post_register_hooks(registered_name, registered_tool)

        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.REGISTER,
                tool_name=registered_name,
            )
        )

        if replaced:
            self._emit_change(
                ChangeEvent(
                    event_type=ChangeEventType.REPLACE,
                    tool_name=registered_name,
                    metadata={"replaced_tool": existing},
                )
            )

        # Emit the warning last.  When warnings are configured as errors
        # (e.g. ``-W error``), the exception must not skip the post-register
        # hook or the change events above: listeners would otherwise be left
        # with the old tool in their caches and no event to correct it.
        if replaced and not allow_replace:
            replacement_warning = (
                f"Tool {registered_name!r} was already registered; the "
                "previous definition was discarded. Pass allow_replace=True "
                "to acknowledge replacement."
            )
            if was_overridden:
                replacement_warning += " The recorded override was also discarded."
            warn_at_user_frame(replacement_warning, UserWarning)

        return tool_or_func

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
        self._overrides.pop(name, None)
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.UNREGISTER,
                tool_name=name,
            )
        )
        return True

    def _replace_tool(self, name: str, **updates: object) -> Tool:
        """Replace a registered tool with an updated copy.

        Creates a new ``Tool`` via ``dataclasses.replace()`` with the
        given field overrides and stores it back in the registry.

        Args:
            name: Registered tool name.
            **updates: Field-value pairs forwarded to
                ``dataclasses.replace()``.

        Returns:
            The newly created ``Tool`` instance.
        """
        assert "name" not in updates, (
            "_replace_tool cannot change 'name'; it would create a "
            "key/value mismatch in _tools"
        )
        old = self._tools[name]
        new_tool = dataclasses.replace(old, **updates)
        self._tools[name] = new_tool
        return new_tool

    def _replace_tool_metadata(self, name: str, **meta_updates: object) -> Tool:
        """Replace a registered tool's metadata with updated fields.

        Creates a new ``ToolMetadata`` via ``dataclasses.replace()`` with
        the given overrides, then replaces the ``Tool`` itself.

        Args:
            name: Registered tool name.
            **meta_updates: Field-value pairs forwarded to
                ``dataclasses.replace()`` on the tool's metadata.

        Returns:
            The newly created ``Tool`` instance.
        """
        old = self._tools[name]
        new_meta = dataclasses.replace(old.metadata, **meta_updates)
        new_tool = dataclasses.replace(old, metadata=new_meta)
        self._tools[name] = new_tool
        return new_tool

    # ------------------------------------------------------------------ #
    #  Tool override                                                      #
    # ------------------------------------------------------------------ #

    def override(
        self,
        name: str,
        tool: Tool | Callable,
        *,
        create: bool = False,
    ) -> Tool:
        """Replace a registered tool with a new implementation.

        The currently registered ``Tool`` under *name* is recorded in an
        internal ``_overrides`` map so it can be restored later with
        :meth:`restore_override`, and ``_tools[name]`` is swapped for *tool*.
        An :attr:`ChangeEventType.OVERRIDE` event is emitted.

        Args:
            name: Registered name of the tool to override.
            tool: Replacement ``Tool`` instance or plain callable.  A bare
                callable is converted with ``Tool.from_function`` using
                *name* as the tool name.
            create: When ``True``, register *tool* under *name* even when no
                tool is currently registered.  Defaults to ``False``.

        Returns:
            The replacement ``Tool`` now stored in the registry.

        Raises:
            KeyError: If *name* is not registered and *create* is ``False``.

        Note:
            - The registry key stays *name*; the replacement's own ``name``
              field is aligned to it.
            - Disabled state is preserved: overriding a disabled tool
              replaces its behaviour without re-enabling it.
            - A plain :meth:`register` onto an overridden name supersedes the
              override and drops the record, because the new tool becomes the
              current definition.
            - When *create* is ``True`` and nothing was registered, the tool
              is treated as new: post-register hooks run and a ``REGISTER``
              event is emitted alongside ``OVERRIDE``.  No displaced tool is
              recorded, so :meth:`restore_override` raises :class:`KeyError`
              for *name*.
            - Only the tool displaced by the *first* override is recorded;
              repeated overrides keep the original restorable.
        """
        existing = self._tools.get(name)
        created = existing is None
        if created and not create:
            raise KeyError(f"Tool not registered: {name}")

        new_tool = self._coerce_override_tool(name, tool)
        if existing is not None and name not in self._overrides:
            self._overrides[name] = existing

        self._tools[name] = new_tool
        if created:
            self._run_post_register_hooks(name, new_tool)
            self._emit_change(
                ChangeEvent(event_type=ChangeEventType.REGISTER, tool_name=name)
            )
        self._emit_change(
            ChangeEvent(event_type=ChangeEventType.OVERRIDE, tool_name=name)
        )
        return new_tool

    def restore_override(self, name: str) -> Tool:
        """Restore the tool displaced by :meth:`override`.

        Args:
            name: Name whose override should be reverted.

        Returns:
            The displaced ``Tool`` that is installed back under *name*.

        Raises:
            KeyError: If no override is recorded for *name*, or if no tool is
                currently registered under *name*.
        """
        displaced = self._overrides.get(name)
        if displaced is None:
            raise KeyError(f"No override recorded for: {name}")
        if name not in self._tools:
            # The name was renamed or removed underneath the override, so the
            # record can no longer be installed.  Drop it and refuse.
            del self._overrides[name]
            raise KeyError(
                f"Cannot restore override for {name!r}: no tool is registered "
                f"under that name."
            )
        del self._overrides[name]
        self._tools[name] = displaced
        self._emit_change(
            ChangeEvent(
                event_type=ChangeEventType.OVERRIDE,
                tool_name=name,
                metadata={"restored": True},
            )
        )
        return displaced

    def list_overrides(self) -> dict[str, Tool]:
        """Return the tools currently displaced by overrides.

        Returns:
            A copy of the ``{name: displaced_tool}`` mapping.  Mutating the
            returned dict does not affect the registry.
        """
        return dict(self._overrides)

    def _update_override_record(self, name: str, tool: Tool) -> None:
        """Re-record the displaced definition for an active override.

        Remote-source refreshes call this when the remote still serves
        *name*: the override keeps winning, but the recorded "what to restore"
        tool is updated to the current remote definition.  A later
        :meth:`restore_override` therefore reverts to what the remote serves
        now, not to a stale generation.

        Args:
            name: Registered name that is currently overridden.
            tool: The tool the remote source now serves for *name*.
        """
        if name in self._overrides:
            self._overrides[name] = tool

    def _coerce_override_tool(self, name: str, tool: Tool | Callable) -> Tool:
        """Normalise an override target into a ``Tool`` keyed by *name*.

        The registry key is authoritative: the replacement's ``name`` is set to
        *name* exactly (``Tool.from_function`` would normalize the separator
        away and break the key/name invariant).  Namespace and method name are
        derived from the key so later namespace operations can rebuild it.
        """
        if isinstance(tool, Tool):
            base = tool
        else:
            base = Tool.from_function(tool, name=name)

        sep = self.name_sep
        if sep in name:
            namespace, method_name = name.split(sep, 1)
        else:
            namespace, method_name = None, name

        return dataclasses.replace(
            base,
            name=name,
            namespace=namespace,
            method_name=method_name,
        )

    def _register_class(self, cls_or_instance, *, namespace, **kwargs):
        traverse_mro = kwargs.pop("traverse_mro", True)
        constructor_kwargs = kwargs.pop("constructor_kwargs", None)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        from ..integrations.native import ClassToolIntegration

        hub = ClassToolIntegration(
            cast("ToolRegistry", self), traverse_mro=traverse_mro
        )
        return hub.register_class_methods(
            cls_or_instance, namespace, constructor_kwargs, **replace_kwargs
        )

    async def _register_class_async(self, cls_or_instance, *, namespace, **kwargs):
        traverse_mro = kwargs.pop("traverse_mro", True)
        constructor_kwargs = kwargs.pop("constructor_kwargs", None)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        from ..integrations.native import ClassToolIntegration

        hub = ClassToolIntegration(
            cast("ToolRegistry", self), traverse_mro=traverse_mro
        )
        return await hub.register_class_methods_async(
            cls_or_instance, namespace, constructor_kwargs, **replace_kwargs
        )

    def _register_mcp(self, transport, *, namespace, **kwargs):
        persistent = kwargs.pop("persistent", True)
        headers = kwargs.pop("headers", None)
        filter_kwargs = _pop_filter_kwargs(kwargs)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(cast("ToolRegistry", self))
        mcp.register_mcp_tools(
            transport,
            namespace,
            persistent,
            headers=headers,
            **filter_kwargs,
            **replace_kwargs,
        )
        if mcp not in self._mcp_integrations:
            self._mcp_integrations.append(mcp)

    async def _register_mcp_async(self, transport, *, namespace, **kwargs):
        persistent = kwargs.pop("persistent", True)
        headers = kwargs.pop("headers", None)
        filter_kwargs = _pop_filter_kwargs(kwargs)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        MCPIntegration = _import_mcp_integration()
        mcp = MCPIntegration(cast("ToolRegistry", self))
        await mcp.register_mcp_tools_async(
            transport,
            namespace,
            persistent,
            headers=headers,
            **filter_kwargs,
            **replace_kwargs,
        )
        if mcp not in self._mcp_integrations:
            self._mcp_integrations.append(mcp)

    def _register_openapi(self, client, *, namespace, **kwargs):
        openapi_spec = kwargs.pop("openapi_spec", None)
        if openapi_spec is None:
            raise TypeError(
                "source='openapi' requires an openapi_spec=... keyword argument."
            )
        persistent = kwargs.pop("persistent", True)
        spec_url = kwargs.pop("spec_url", None)
        filter_kwargs = _pop_filter_kwargs(kwargs)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(cast("ToolRegistry", self))
        openapi.register_openapi_tools(
            client,
            openapi_spec,
            namespace,
            persistent,
            spec_url=spec_url,
            **filter_kwargs,
            **replace_kwargs,
        )
        if openapi not in self._openapi_integrations:
            self._openapi_integrations.append(openapi)

    async def _register_openapi_async(self, client, *, namespace, **kwargs):
        openapi_spec = kwargs.pop("openapi_spec", None)
        if openapi_spec is None:
            raise TypeError(
                "source='openapi' requires an openapi_spec=... keyword argument."
            )
        persistent = kwargs.pop("persistent", True)
        spec_url = kwargs.pop("spec_url", None)
        filter_kwargs = _pop_filter_kwargs(kwargs)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        OpenAPIIntegration = _import_openapi_integration()
        openapi = OpenAPIIntegration(cast("ToolRegistry", self))
        await openapi.register_openapi_tools_async(
            client,
            openapi_spec,
            namespace,
            persistent,
            spec_url=spec_url,
            **filter_kwargs,
            **replace_kwargs,
        )
        if openapi not in self._openapi_integrations:
            self._openapi_integrations.append(openapi)

    def _register_langchain(self, langchain_tool, *, namespace, **kwargs):
        filter_kwargs = _pop_filter_kwargs(kwargs)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        LangChainIntegration = _import_langchain_integration()
        langchain = LangChainIntegration(cast("ToolRegistry", self))
        return langchain.register_langchain_tools(
            langchain_tool, namespace, **filter_kwargs, **replace_kwargs
        )

    async def _register_langchain_async(self, langchain_tool, *, namespace, **kwargs):
        filter_kwargs = _pop_filter_kwargs(kwargs)
        replace_kwargs = _forward_allow_replace(kwargs.pop("allow_replace", False))
        LangChainIntegration = _import_langchain_integration()
        langchain = LangChainIntegration(cast("ToolRegistry", self))
        return await langchain.register_langchain_tools_async(
            langchain_tool, namespace, **filter_kwargs, **replace_kwargs
        )

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
