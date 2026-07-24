import json
import logging
import random
import string
import time
import traceback as tb_module
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal
from collections.abc import Callable

from .executor import InlineBackend, ProcessPoolBackend, ThreadBackend
from .tool import ToolTag

if TYPE_CHECKING:
    from .executor import ExecutionBackend
    from .tool import Tool
from .llm.truncation import truncate_result
from .llm.content_blocks import is_content_block_list
from .permissions import (
    PermissionResult,
)
from .llm.tool_calls import (
    API_FORMATS,
    ErrorResult,
    ResultList,
    ToolCallResult,
    build_assistant_messages,
    build_tool_result_messages,
    convert_tool_calls,
)

from .events import ChangeCallback, ChangeEvent, ChangeEventType
from .llm.discovery import (
    TOOL_DISCOVERY_NAME,
    ToolDiscoveryTool,
    _BASE_DISCOVERY_DESCRIPTION,
)
from .runtimes._ptc_controller import PtcController

from ._mixins import (
    AdminMixin,
    ChangeCallbackMixin,
    EnableDisableMixin,
    ExecutionLoggingMixin,
    NamespaceMixin,
    PermissionsMixin,
    RegistrationMixin,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ToolError:
    """Internal sentinel for structured error propagation.

    Used by ``_collect_handle_result`` and ``_submit_tool_call`` to carry
    exception metadata through the execution pipeline without relying on
    string-prefix detection.
    """

    message: str
    exception_type: str | None = None
    traceback_str: str | None = None
    is_timeout: bool = False

    def format(self) -> str:
        """Return the ``"ExceptionType: message"`` string (or bare message)."""
        prefix = f"{self.exception_type}: " if self.exception_type else ""
        return f"{prefix}{self.message}"

    def to_error_result(self, tool_call: Any) -> "ErrorResult":
        """Convert to a public ErrorResult."""
        return ErrorResult(
            id=tool_call.id,
            name=tool_call.name,
            message=self.format(),
        )


class ToolRegistry(
    AdminMixin,
    ExecutionLoggingMixin,
    PermissionsMixin,
    RegistrationMixin,
    EnableDisableMixin,
    NamespaceMixin,
    ChangeCallbackMixin,
):
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
    def __init__(
        self,
        name: str | None = None,
        *,
        default_max_result_size: int | None = None,
        think_augment: bool = False,
        tool_discovery: bool = False,
        name_sep: Literal["-", "."] = "-",
    ) -> None:
        """Initialize an empty ToolRegistry.

        This method initializes an empty ToolRegistry with a name and internal
        structures for storing tools and sub-registries.

        Args:
            name: Name of the tool registry. Defaults to a random
                "reg_<4-char>" string. For instance, "reg_1a3c".
            default_max_result_size: Default maximum result size in characters
                for all tools. Individual tools can override this via
                ``ToolMetadata.max_result_size``. None means no limit.
            think_augment: Enable thought-augmented tool calling globally.
                When ``True``, a ``toolcall_reason`` property is
                included in every tool's schema so LLMs can articulate
                their rationale when calling tools.  Individual tools
                can override this via ``ToolMetadata.think_augment``.
                Defaults to ``False``.
            tool_discovery: Enable tool discovery on initialization.
                When ``True``, :meth:`enable_tool_discovery` is called
                automatically, registering a ``discover_tools`` tool
                that LLMs can use to discover other tools by exact
                name or natural language query.
                Defaults to ``False``.
            name_sep: Separator character used when combining namespace and
                method name into a tool name (e.g. ``"calculator-evaluate"``
                with ``"-"`` or ``"calculator.evaluate"`` with ``"."``).
                OpenAI requires ``"-"``; some providers allow ``"."``.
                Defaults to ``"-"``.

        Notes:
            This class uses private attributes `_tools` and `_sub_registries` internally
            to manage registered tools and sub-registries. These are not intended for
            external use.
        """
        super().__init__()
        if name is None:
            name = f"reg_{''.join(random.sample(string.hexdigits.lower(), 4))}"
        self.name = name
        self._thread_backend = ThreadBackend()
        self._process_backend = ProcessPoolBackend()
        self._inline_backend = InlineBackend()
        self._execution_mode: Literal["process", "thread"] = "process"
        self._default_max_result_size = default_max_result_size
        self._think_augment = think_augment
        self._name_sep: Literal["-", "."] = name_sep
        self._tool_discovery: ToolDiscoveryTool | None = None
        self._tool_discovery_callback: ChangeCallback | None = None
        self._ptc = PtcController(self)

        if tool_discovery:
            self.enable_tool_discovery()

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
        return json.dumps(self.get_schemas(), indent=2)

    def __str__(self):
        """Return the JSON representation of the registry as a string.

        Returns:
            str: JSON string representation of the registry.
        """
        return json.dumps(self.get_schemas(), indent=2)

    def __getitem__(self, key: str) -> Callable[..., Any] | None:
        """Enable key-value access to retrieve callables.

        Args:
            key (str): Name of the function.

        Returns:
            Optional[Callable[..., Any]]: The function to call, or None if not found.
        """
        return self.get_callable(key)

    # ============== Lifecycle ==============
    async def close_async(self) -> None:
        """Close all persistent connections (async).

        Closes MCP and OpenAPI integrations that hold persistent
        connections or HTTP clients.
        """
        for integration in self._mcp_integrations:
            await integration.close()
        for integration in self._openapi_integrations:
            await integration.close_async()
        self._mcp_integrations.clear()
        self._openapi_integrations.clear()

    def close(self) -> None:
        """Close all persistent connections (sync)."""
        for integration in self._mcp_integrations:
            integration.close_sync()
        self._mcp_integrations.clear()
        for integration in self._openapi_integrations:
            integration.close()
        self._openapi_integrations.clear()

    async def __aenter__(self) -> "ToolRegistry":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close_async()

    def __enter__(self) -> "ToolRegistry":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ============== Think-augment toggle ==============
    def enable_think_augment(self) -> None:
        """Enable thought-augmented tool calling globally.

        When enabled, a ``toolcall_reason`` property is included in
        every tool's schema (via :meth:`get_schemas`) so that LLMs can
        articulate their rationale when calling tools.  Individual tools
        can still override this via ``ToolMetadata.think_augment``.

        Reference: https://arxiv.org/abs/2601.18282
        """
        self._think_augment = True

    def disable_think_augment(self) -> None:
        """Disable thought-augmented tool calling globally.

        When disabled, the ``toolcall_reason`` property is stripped from
        tool schemas produced by :meth:`get_schemas`, unless a tool
        explicitly opts in via ``ToolMetadata.think_augment = True``.
        """
        self._think_augment = False

    # ============== Tool discovery toggle ==============
    def enable_tool_discovery(
        self,
        field_weights: dict[str, float] | None = None,
    ) -> ToolDiscoveryTool:
        """Enable tool discovery and register a discovery tool.

        Creates a :class:`ToolDiscoveryTool`, registers its
        :meth:`~ToolDiscoveryTool.discover` method as a callable tool
        named ``discover_tools``, and subscribes to registry change
        events for automatic index rebuilds.

        The discovery tool itself is never deferred (``defer=False``)
        so that LLMs always see it in the initial schema.

        Args:
            field_weights: Optional per-field BM25F boost weights.

        Returns:
            The :class:`ToolDiscoveryTool` instance.
        """
        from .tool import Tool, ToolMetadata

        if self._tool_discovery is not None:
            return self._tool_discovery

        discoverer = ToolDiscoveryTool(self, field_weights=field_weights)

        discovery_tool = Tool.from_function(
            discoverer.discover,
            name=TOOL_DISCOVERY_NAME,
            description=_BASE_DISCOVERY_DESCRIPTION,
            metadata=ToolMetadata(defer=False),
        )
        self.register(discovery_tool)
        # Sync description now that discover_tools is registered and deferred
        # tools are known.
        discoverer._sync_description()

        def _on_registry_change(event: ChangeEvent) -> None:
            if event.event_type in {
                ChangeEventType.REGISTER,
                ChangeEventType.UNREGISTER,
            }:
                if event.tool_name != TOOL_DISCOVERY_NAME:
                    discoverer.rebuild_index()
            elif event.event_type in {
                ChangeEventType.ENABLE,
                ChangeEventType.DISABLE,
                ChangeEventType.METADATA_UPDATE,
            }:
                if event.tool_name != TOOL_DISCOVERY_NAME:
                    # Cheap sync — no full index rebuild needed, just update
                    # the discover_tools description to reflect current state.
                    discoverer._sync_description()

        self.on_change(_on_registry_change)

        self._tool_discovery = discoverer
        self._tool_discovery_callback = _on_registry_change
        return discoverer

    def disable_tool_discovery(self) -> None:
        """Disable tool discovery and unregister the discovery tool."""
        if self._tool_discovery is None:
            return

        # Remove the discovery tool from registry
        self._tools.pop(TOOL_DISCOVERY_NAME, None)

        # Remove the change callback
        if self._tool_discovery_callback is not None:
            self.remove_on_change(self._tool_discovery_callback)
            self._tool_discovery_callback = None

        self._tool_discovery = None

    # ============== PTC (Programmatic Tool Calling) ==============
    @property
    def ptc(self) -> PtcController:
        """PTC (Programmatic Tool Calling) controller.

        Use ``registry.ptc.enable()`` to register a ``code_execution``
        tool that lets LLMs write Python code with registered tools
        callable in the namespace.

        Example::

            registry.ptc.enable(timeout=30)
            registry.ptc.disable()
            registry.ptc.enabled           # bool
            registry.ptc.last_invocation_id  # str | None
        """
        return self._ptc

    # ============== Execution helpers (shared by invoke + execute_tool_calls) ==

    @staticmethod
    def _clean_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
        """Drop the synthetic ``toolcall_reason`` key before execution."""
        return {k: v for k, v in kwargs.items() if k != "toolcall_reason"}

    def _backend_for(self, name: str) -> "ExecutionBackend":
        """Map a backend name to its backend instance."""
        if name == "thread":
            return self._thread_backend
        if name == "process":
            return self._process_backend
        return self._inline_backend

    def _resolve_backend(
        self,
        tool: "Tool | None",
        execution_mode: str | None = None,
        default: str = "inline",
    ) -> "ExecutionBackend":
        """Resolve the execution backend for a single tool.

        This is the seam that decouples the calling interface from the
        execution backend.  Resolution order:

        1. Explicit caller ``execution_mode`` (``"thread"``/``"process"``).
        2. The tool's ``metadata.natural_backend`` hint.
        3. The *default* backend for the calling context.

        The default differs by entry point: single-tool ``invoke`` passes
        ``"inline"`` (zero overhead, no cross-thread hop), while
        ``execute_tool_calls`` passes the registry's ``_execution_mode``
        (``"process"`` by default) so plain Python tools still get CPU
        isolation in a batch.

        Future isolation backends (e.g. a sandbox) plug in here without
        touching ``invoke``/``ainvoke``.

        Args:
            tool: The :class:`Tool` to execute.
            execution_mode: Optional caller override.
            default: Backend name to use when neither an explicit mode nor
                a ``natural_backend`` hint applies.

        Returns:
            An execution backend instance.
        """
        if execution_mode in ("thread", "process"):
            return self._backend_for(execution_mode)

        metadata = getattr(tool, "metadata", None)
        natural = getattr(metadata, "natural_backend", None) if metadata else None
        if natural in ("inline", "thread", "process"):
            return self._backend_for(natural)

        return self._backend_for(default)

    def _check_tool_access(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        invocation_id: str | None = None,
    ) -> "Tool":
        """Check that a tool exists, is enabled, and passes permission.

        This is the single callsite for access control — both
        :meth:`invoke` and :meth:`execute_tool_calls` use it.

        Args:
            tool_name: Name of the registered tool.
            kwargs: Arguments (used for permission evaluation).
            invocation_id: Invocation ID for log entries.

        Returns:
            The :class:`Tool` object if access is granted.

        Raises:
            KeyError: If the tool is not registered.
            RuntimeError: If the tool is disabled.
            PermissionError: If denied by permission policy.
        """
        from .admin import ExecutionStatus

        tool_obj = self.get_tool(tool_name)
        if tool_obj is None:
            raise KeyError(f"Tool '{tool_name}' is not registered")

        if not self.is_enabled(tool_name):
            reason = self.get_disable_reason(tool_name) or "Tool is disabled"
            self._log_entry(
                tool_name,
                ExecutionStatus.DISABLED,
                0.0,
                kwargs,
                error=reason,
                invocation_id=invocation_id,
            )
            raise RuntimeError(f"Tool '{tool_name}' is disabled: {reason}")

        decision = self._resolve_permission(tool_obj, kwargs)
        if decision == PermissionResult.DENY:
            self._log_entry(
                tool_name,
                ExecutionStatus.ERROR,
                0.0,
                kwargs,
                error="Denied by permission policy",
                invocation_id=invocation_id,
            )
            raise PermissionError(f"Tool '{tool_name}' denied by permission policy")

        return tool_obj

    def _log_tool_result(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        *,
        result: Any = None,
        error: _ToolError | Exception | None = None,
        duration_ms: float = 0.0,
        invocation_id: str | None = None,
    ) -> None:
        """Log a tool execution result and emit error events.

        This is the single callsite for result logging — both
        :meth:`invoke` and :meth:`execute_tool_calls` use it.

        Args:
            tool_name: Name of the executed tool.
            kwargs: Arguments passed to the tool.
            result: Return value on success.
            error: A :class:`_ToolError` or :class:`Exception` on failure.
            duration_ms: Execution duration in milliseconds.
            invocation_id: Invocation ID for log grouping.
        """
        from .admin import ExecutionStatus

        if error is not None:
            if isinstance(error, _ToolError):
                status = (
                    ExecutionStatus.TIMEOUT
                    if error.is_timeout
                    else ExecutionStatus.ERROR
                )
                self._log_entry(
                    tool_name,
                    status,
                    duration_ms,
                    kwargs,
                    error=error.message,
                    exception_type=error.exception_type,
                    traceback=error.traceback_str,
                    invocation_id=invocation_id,
                )
            else:
                self._log_entry(
                    tool_name,
                    ExecutionStatus.ERROR,
                    duration_ms,
                    kwargs,
                    error=str(error),
                    exception_type=type(error).__qualname__,
                    traceback=tb_module.format_exc(),
                    invocation_id=invocation_id,
                )
            exc_type = (
                error.exception_type
                if isinstance(error, _ToolError)
                else type(error).__qualname__
            )
            self._emit_change(
                ChangeEvent(
                    event_type=ChangeEventType.TOOL_ERROR,
                    tool_name=tool_name,
                    reason=str(error),
                    metadata={
                        "exception_type": exc_type,
                        "arguments": kwargs,
                    },
                )
            )
        else:
            self._log_entry(
                tool_name,
                ExecutionStatus.SUCCESS,
                duration_ms,
                kwargs,
                result=str(result) if result is not None else None,
                invocation_id=invocation_id,
            )

    # ============== Execution ==============
    def _prepare_call(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        invocation_id: str | None,
    ) -> Any | _ToolError:
        """Run access control for a single call.

        Returns the :class:`Tool` when access is granted, or a
        :class:`_ToolError` when the tool is missing, disabled, or denied
        — so callers can produce an ``ErrorResult`` instead of raising.
        """
        try:
            return self._check_tool_access(tool_name, kwargs, invocation_id)
        except (KeyError, RuntimeError, PermissionError) as exc:
            return _ToolError(
                message=str(exc),
                exception_type=type(exc).__qualname__,
            )

    def _invoke_raw(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        *,
        invocation_id: str | None = None,
        execution_mode: Literal["thread", "process"] | None = None,
    ) -> Any:
        """Execute a single tool and return the **raw** result.

        Internal variant of :meth:`invoke` that runs the same pipeline
        (permission check, backend seam, logging) but returns the tool's
        raw Python value and **raises** on failure — instead of wrapping
        into a ``Result``.

        Used by PTC, whose LLM-authored code composes tool outputs
        naturally (e.g. ``s = add(a=1, b=2) + tax``) and therefore needs
        real Python values, not finalized strings.

        Raises:
            KeyError / RuntimeError / PermissionError: On access failure.
            Exception: Any exception raised by the tool itself.
        """
        from .utils import generate_invocation_id

        if invocation_id is None:
            invocation_id = generate_invocation_id("sig")

        # Access control raises here (raw path), matching legacy invoke().
        tool_obj = self._check_tool_access(tool_name, kwargs, invocation_id)
        backend = self._resolve_backend(tool_obj, execution_mode)
        clean_kwargs = self._clean_kwargs(kwargs)
        per_call_timeout = tool_obj.metadata.timeout if tool_obj.metadata else None

        start = time.perf_counter()
        try:
            handle = backend.submit(
                lambda **kw: tool_obj.run(kw),
                clean_kwargs,
                execution_id=invocation_id,
                timeout=per_call_timeout,
            )
            result = handle.result()
            duration_ms = (time.perf_counter() - start) * 1000
            self._log_tool_result(
                tool_name,
                kwargs,
                result=result,
                duration_ms=duration_ms,
                invocation_id=invocation_id,
            )
            return result
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            self._log_tool_result(
                tool_name,
                kwargs,
                error=exc,
                duration_ms=duration_ms,
                invocation_id=invocation_id,
            )
            raise

    def invoke(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        *,
        invocation_id: str | None = None,
        execution_mode: Literal["thread", "process"] | None = None,
    ) -> ToolCallResult | ErrorResult:
        """Execute a single tool and return a structured result.

        Canonical single-tool entry point.  Runs the full pipeline
        (permissions, execution via the resolved backend, logging) and
        returns a :class:`ToolCallResult` on success or an
        :class:`ErrorResult` on any failure — including access-control
        failures (missing/disabled/denied).  **Never raises** for those
        conditions, mirroring :meth:`execute_tool_calls`.

        Args:
            tool_name: Name of the registered tool.
            kwargs: Keyword arguments to pass to the tool.
            invocation_id: Optional ID to group related calls.  If
                ``None``, a ``tr_sig_`` ID is auto-generated and used as
                the result ``id``.
            execution_mode: Optional backend override
                (``"thread"``/``"process"``).  Defaults to the tool's
                natural backend (inline for most single calls).

        Returns:
            ``ToolCallResult`` on success, ``ErrorResult`` on failure.
        """
        from .utils import generate_invocation_id

        if invocation_id is None:
            invocation_id = generate_invocation_id("sig")

        prepared = self._prepare_call(tool_name, kwargs, invocation_id)
        if isinstance(prepared, _ToolError):
            return ErrorResult(
                id=invocation_id,
                name=tool_name,
                message=prepared.format(),
            )

        tool_obj = prepared
        backend = self._resolve_backend(tool_obj, execution_mode)
        clean_kwargs = self._clean_kwargs(kwargs)
        per_call_timeout = tool_obj.metadata.timeout if tool_obj.metadata else None

        start = time.perf_counter()
        # Submit tool_obj.run so the sync path is forced regardless of any
        # ambient event loop (BaseToolWrapper.__call__ would auto-select
        # async based on a running loop).  The backend calls fn(**kwargs),
        # so the thunk collects them back into the dict run() expects.
        handle = backend.submit(
            lambda **kw: tool_obj.run(kw),
            clean_kwargs,
            execution_id=invocation_id,
            timeout=per_call_timeout,
        )
        outcome = self._collect_handle_result(handle, tool_name)
        duration_ms = (time.perf_counter() - start) * 1000

        if isinstance(outcome, _ToolError):
            self._log_tool_result(
                tool_name,
                kwargs,
                error=outcome,
                duration_ms=duration_ms,
                invocation_id=invocation_id,
            )
            return ErrorResult(
                id=invocation_id,
                name=tool_name,
                message=outcome.format(),
            )

        self._log_tool_result(
            tool_name,
            kwargs,
            result=outcome,
            duration_ms=duration_ms,
            invocation_id=invocation_id,
        )
        return ToolCallResult(id=invocation_id, name=tool_name, result=outcome)

    async def _acheck_tool_access(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        invocation_id: str | None = None,
    ) -> "Tool":
        """Async access control using :meth:`_aresolve_permission`.

        Mirrors :meth:`_check_tool_access` but awaits async permission
        handlers natively instead of bridging through a thread pool.

        Returns the :class:`Tool` on success; raises ``KeyError`` /
        ``RuntimeError`` / ``PermissionError`` on failure.
        """
        from .admin import ExecutionStatus

        tool_obj = self.get_tool(tool_name)
        if tool_obj is None:
            raise KeyError(f"Tool '{tool_name}' is not registered")

        if not self.is_enabled(tool_name):
            reason = self.get_disable_reason(tool_name) or "Tool is disabled"
            self._log_entry(
                tool_name,
                ExecutionStatus.DISABLED,
                0.0,
                kwargs,
                error=reason,
                invocation_id=invocation_id,
            )
            raise RuntimeError(f"Tool '{tool_name}' is disabled: {reason}")

        decision = await self._aresolve_permission(tool_obj, kwargs)
        if decision == PermissionResult.DENY:
            self._log_entry(
                tool_name,
                ExecutionStatus.ERROR,
                0.0,
                kwargs,
                error="Denied by permission policy",
                invocation_id=invocation_id,
            )
            raise PermissionError(f"Tool '{tool_name}' denied by permission policy")

        return tool_obj

    async def _aprepare_call(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        invocation_id: str | None,
    ) -> Any | _ToolError:
        """Async access control returning ``Tool`` or ``_ToolError``."""
        try:
            return await self._acheck_tool_access(tool_name, kwargs, invocation_id)
        except (KeyError, RuntimeError, PermissionError) as exc:
            return _ToolError(
                message=str(exc),
                exception_type=type(exc).__qualname__,
            )

    async def ainvoke(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        *,
        invocation_id: str | None = None,
        execution_mode: Literal["thread", "process"] | None = None,
    ) -> ToolCallResult | ErrorResult:
        """Async counterpart to :meth:`invoke`.

        For inline-resolved tools (the default, including MCP/OpenAPI),
        awaits ``tool.arun()`` directly on the caller's loop — the tool's
        async transport stays on the running loop without blocking it.
        For thread/process backends, submits and awaits
        ``handle.result_async()``.

        Returns a :class:`ToolCallResult` on success or an
        :class:`ErrorResult` on any failure.  **Never raises** for
        access-control failures.

        Args:
            tool_name: Name of the registered tool.
            kwargs: Keyword arguments to pass to the tool.
            invocation_id: Optional grouping ID; auto-generated
                (``tr_sig_``) when ``None`` and used as the result ``id``.
            execution_mode: Optional backend override.

        Returns:
            ``ToolCallResult`` on success, ``ErrorResult`` on failure.
        """
        from .utils import generate_invocation_id

        if invocation_id is None:
            invocation_id = generate_invocation_id("sig")

        prepared = await self._aprepare_call(tool_name, kwargs, invocation_id)
        if isinstance(prepared, _ToolError):
            return ErrorResult(
                id=invocation_id,
                name=tool_name,
                message=prepared.format(),
            )

        tool_obj = prepared
        backend = self._resolve_backend(tool_obj, execution_mode)
        clean_kwargs = self._clean_kwargs(kwargs)
        per_call_timeout = tool_obj.metadata.timeout if tool_obj.metadata else None

        start = time.perf_counter()
        outcome: Any
        try:
            # Inline backend: pass tool.arun so result_async() can
            # await the coroutine natively on the caller's loop.
            # Pool backends: pass tool.run (sync) for execution in
            # the worker thread/process.
            if backend is self._inline_backend:
                submit_fn = lambda **kw: tool_obj.arun(kw)  # noqa: E731
            else:
                submit_fn = lambda **kw: tool_obj.run(kw)  # noqa: E731
            handle = backend.submit(
                submit_fn,
                clean_kwargs,
                execution_id=invocation_id,
                timeout=per_call_timeout,
            )
            raw = await handle.result_async()
            outcome = self._finalize_result(raw, tool_name)
        except TimeoutError:
            outcome = _ToolError(
                message=f"Error: Tool '{tool_name}' timed out",
                exception_type="TimeoutError",
                is_timeout=True,
            )
        except Exception as exc:
            outcome = _ToolError(
                message=f"Error executing {tool_name}: {exc!s}",
                exception_type=type(exc).__qualname__,
                traceback_str=tb_module.format_exc(),
            )
        duration_ms = (time.perf_counter() - start) * 1000

        if isinstance(outcome, _ToolError):
            self._log_tool_result(
                tool_name,
                kwargs,
                error=outcome,
                duration_ms=duration_ms,
                invocation_id=invocation_id,
            )
            return ErrorResult(
                id=invocation_id,
                name=tool_name,
                message=outcome.format(),
            )

        self._log_tool_result(
            tool_name,
            kwargs,
            result=outcome,
            duration_ms=duration_ms,
            invocation_id=invocation_id,
        )
        return ToolCallResult(id=invocation_id, name=tool_name, result=outcome)

    def _finalize_result(self, result: Any, tool_name: str) -> str | list:
        """Convert a raw tool result to a string or content block list.

        Multimodal results (lists of content blocks with ``"type"`` keys)
        are preserved as-is so that downstream formatters can handle them
        per API format.  All other results are serialized to strings.

        Args:
            result: Raw result from tool execution.
            tool_name: Name of the tool (used to look up ``max_result_size``).

        Returns:
            The result as a string (possibly truncated), or a
            ``list[ContentBlock]`` for multimodal results.
        """
        # Preserve multimodal content block lists
        if is_content_block_list(result):
            # Truncate only text blocks if max_result_size is set
            tool_obj = self._tools.get(tool_name)
            max_size = None
            if tool_obj and tool_obj.metadata.max_result_size is not None:
                max_size = tool_obj.metadata.max_result_size
            elif self._default_max_result_size is not None:
                max_size = self._default_max_result_size

            if max_size is not None:
                result = self._truncate_content_blocks(result, max_size, tool_name)
            return result

        # Serialize to string
        try:
            json.dumps(result)
        except (TypeError, ValueError):
            result = str(result)
        result_str: str = result if isinstance(result, str) else json.dumps(result)

        # Determine effective max size
        tool_obj = self._tools.get(tool_name)
        max_size = None
        if tool_obj and tool_obj.metadata.max_result_size is not None:
            max_size = tool_obj.metadata.max_result_size
        elif self._default_max_result_size is not None:
            max_size = self._default_max_result_size

        if max_size is not None:
            tr = truncate_result(result_str, max_size, tool_name=tool_name)
            return str(tr)
        return result_str

    @staticmethod
    def _truncate_content_blocks(blocks: list, max_size: int, tool_name: str) -> list:
        """Truncate text blocks within a content block list.

        Image blocks are left untouched.  Text blocks are truncated
        proportionally so the total text size stays within *max_size*.

        Args:
            blocks: Content block list.
            max_size: Maximum total text size in characters.
            tool_name: Tool name for truncation metadata.

        Returns:
            The (possibly modified) content block list.
        """
        total_text = sum(
            len(b.get("text", "")) for b in blocks if b.get("type") == "text"
        )
        if total_text <= max_size:
            return blocks

        truncated: list = []
        remaining = max_size
        for block in blocks:
            if block.get("type") != "text":
                truncated.append(block)
                continue
            text = block.get("text", "")
            if len(text) <= remaining:
                truncated.append(block)
                remaining -= len(text)
            else:
                tr = truncate_result(
                    text, remaining, tool_name=tool_name, persist=False
                )
                truncated.append({"type": "text", "text": tr.content})
                remaining = 0
        return truncated

    def set_default_execution_mode(self, mode: Literal["thread", "process"]) -> None:
        """Set the default execution mode for parallel tasks.

        This sets the default mode used by :meth:`execute_tool_calls` when no
        per-call ``execution_mode`` override is provided.

        Args:
            mode (Literal["thread", "process"]): The desired execution mode.

        Raises:
            ValueError: If an invalid mode is provided.
        """
        if mode not in {"thread", "process"}:
            raise ValueError("Invalid mode. Choose 'thread' or 'process'.")
        self._execution_mode = mode

    def set_execution_mode(self, mode: Literal["thread", "process"]) -> None:
        """Deprecated: use :meth:`set_default_execution_mode` instead."""
        warnings.warn(
            "set_execution_mode() is deprecated, "
            "use set_default_execution_mode() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.set_default_execution_mode(mode)

    def _classify_tool_calls(
        self,
        generic_tool_calls: list[Any],
        invocation_id: str | None = None,
    ) -> tuple[list[Any], dict[str, Any], dict[str, float], dict[str, dict]]:
        """Separate tool calls into enabled vs disabled/denied, logging rejections.

        Uses :meth:`_check_tool_access` for permission checks so the
        access control logic is shared with :meth:`invoke`.

        Args:
            generic_tool_calls: Normalized tool call list.
            invocation_id: Invocation ID to attach to log entries.

        Returns:
            Tuple of (enabled_calls, tool_responses, call_start_times, call_arguments).
        """
        enabled_calls: list[Any] = []
        tool_responses: dict[str, Any] = {}
        call_start_times: dict[str, float] = {}
        call_arguments: dict[str, dict] = {}

        for tc in generic_tool_calls:
            try:
                args = json.loads(tc.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}

            try:
                self._check_tool_access(tc.name, args, invocation_id)
            except (KeyError, RuntimeError, PermissionError) as exc:
                tool_responses[tc.id] = _ToolError(
                    message=f"Error: {exc}",
                    exception_type=type(exc).__qualname__,
                )
            else:
                enabled_calls.append(tc)
                call_start_times[tc.id] = time.perf_counter()
                call_arguments[tc.id] = args

        return enabled_calls, tool_responses, call_start_times, call_arguments

    def _log_entry(
        self,
        tool_name: str,
        status: Any,
        duration_ms: float,
        arguments: dict,
        *,
        result: str | None = None,
        error: str | None = None,
        exception_type: str | None = None,
        traceback: str | None = None,
        invocation_id: str | None = None,
    ) -> None:
        """Append an entry to the execution log if logging is enabled.

        Args:
            tool_name: Name of the tool.
            status: Execution status enum value.
            duration_ms: Execution duration in milliseconds.
            arguments: Tool call arguments.
            result: Optional result string.
            error: Optional error string.
            exception_type: Optional qualified exception class name.
            traceback: Optional formatted traceback string.
            invocation_id: Optional invocation ID grouping related calls.
        """
        if self._execution_log is None:
            return
        from .admin import ExecutionLogEntry

        entry = ExecutionLogEntry.create(
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            arguments=arguments,
            result=result,
            error=error,
            exception_type=exception_type,
            traceback=traceback,
            invocation_id=invocation_id,
        )
        self._execution_log.add(entry)

    def _submit_tool_call(
        self,
        tc: Any,
        execution_mode: str | None,
        call_arguments: dict[str, dict],
        backend: Any = None,
    ) -> Any | _ToolError:
        """Submit a single tool call using its resolved backend.

        The backend is resolved per tool via :meth:`_resolve_backend`
        (caller ``execution_mode`` > ``natural_backend`` > registry
        default), so MCP/OpenAPI tools run inline while plain Python
        tools use the batch default (process).

        Args:
            tc: The tool call to submit.
            execution_mode: Optional caller backend override.
            call_arguments: Map of call ID to parsed arguments.
            backend: Pre-resolved backend to reuse.  When ``None`` the
                backend is resolved here; callers that already resolved it
                (e.g. :meth:`_execute_concurrent` grouping) pass it in to
                avoid a redundant resolution.

        Returns:
            An ExecutionHandle on success, or a ``_ToolError`` on failure.
        """
        function_name = tc.name
        function_args = call_arguments.get(tc.id, {})
        tool_obj = self.get_tool(function_name)
        function_args.pop("toolcall_reason", None)
        callable_func = tool_obj.callable if tool_obj else None

        if callable_func is None:
            return _ToolError(
                message=f"Error: Tool '{function_name}' not found or callable is None",
            )

        per_call_timeout = (
            tool_obj.metadata.timeout if tool_obj and tool_obj.metadata else None
        )

        if backend is None:
            backend = self._resolve_backend(
                tool_obj, execution_mode, default=self._execution_mode
            )

        try:
            return backend.submit(
                callable_func,
                function_args,
                execution_id=tc.id,
                timeout=per_call_timeout,
            )
        except Exception as e:
            # Safety net for a plain Python tool that resolved to the
            # process backend but cannot be pickled (e.g. a closure over
            # unpicklable state).  MCP/OpenAPI tools never reach here —
            # they resolve to inline via natural_backend.
            if backend is self._process_backend:
                try:
                    return self._thread_backend.submit(
                        callable_func,
                        function_args,
                        execution_id=tc.id,
                        timeout=per_call_timeout,
                    )
                except Exception as e2:
                    return _ToolError(
                        message=f"Error preparing tool call {function_name}: {e2!s}",
                        exception_type=type(e2).__qualname__,
                        traceback_str=tb_module.format_exc(),
                    )
            return _ToolError(
                message=f"Error preparing tool call {function_name}: {e!s}",
                exception_type=type(e).__qualname__,
                traceback_str=tb_module.format_exc(),
            )

    def _collect_handle_result(
        self, handle: Any, tool_name: str
    ) -> str | list | _ToolError:
        """Wait for a handle and return the finalized result or a ``_ToolError``.

        Args:
            handle: An ExecutionHandle to collect.
            tool_name: Name of the tool (for error messages and finalization).

        Returns:
            The finalized result string/list, or a ``_ToolError`` on failure.
        """
        try:
            result = handle.result()
            return self._finalize_result(result, tool_name)
        except TimeoutError:
            return _ToolError(
                message=f"Error: Tool '{tool_name}' timed out",
                exception_type="TimeoutError",
                is_timeout=True,
            )
        except Exception as e:
            return _ToolError(
                message=f"Error executing {tool_name}: {e!s}",
                exception_type=type(e).__qualname__,
                traceback_str=tb_module.format_exc(),
            )

    def execute_tool_calls(
        self,
        tool_calls: list[Any],
        execution_mode: Literal["process", "thread"] | None = None,
    ) -> ResultList:
        """Execute tool calls and return structured results.

        Disabled tools are rejected with an :class:`ErrorResult` instead
        of being executed.  If logging is enabled, execution details are
        recorded.

        Args:
            tool_calls: List of tool calls to be executed in any supported format.
            execution_mode: Execution mode to use; defaults to the Executor's current mode.

        Returns:
            List of results in the same order as *tool_calls*.  Each
            element is a :class:`ToolCallResult` (success) or
            :class:`ErrorResult` (failure).
        """
        from .utils import generate_invocation_id

        batch_inv_id = generate_invocation_id("bat")

        generic_tool_calls = convert_tool_calls(tool_calls)
        enabled_calls, tool_responses, call_start_times, call_arguments = (
            self._classify_tool_calls(generic_tool_calls, batch_inv_id)
        )

        if not enabled_calls:
            return self._wrap_results(generic_tool_calls, tool_responses)

        has_unsafe = any(
            (tool_obj := self.get_tool(tc.name)) is not None
            and not tool_obj.metadata.is_concurrency_safe
            for tc in enabled_calls
        )

        if has_unsafe:
            raw_results = self._execute_sequential(
                enabled_calls, execution_mode, call_arguments
            )
        else:
            raw_results = self._execute_concurrent(
                enabled_calls, execution_mode, call_arguments
            )
        tool_responses.update(raw_results)

        self._log_tool_call_results(
            enabled_calls, raw_results, call_start_times, call_arguments, batch_inv_id
        )

        return self._wrap_results(generic_tool_calls, tool_responses)

    def _execute_sequential(
        self,
        enabled_calls: list[Any],
        execution_mode: str | None,
        call_arguments: dict[str, dict],
    ) -> dict[str, Any]:
        """Submit + collect each call in order (used when an unsafe tool is present)."""
        raw_results: dict[str, Any] = {}
        for tc in enabled_calls:
            handle_or_error = self._submit_tool_call(tc, execution_mode, call_arguments)
            if isinstance(handle_or_error, _ToolError):
                raw_results[tc.id] = handle_or_error
            else:
                raw_results[tc.id] = self._collect_handle_result(
                    handle_or_error, tc.name
                )
        return raw_results

    def _execute_concurrent(
        self,
        enabled_calls: list[Any],
        execution_mode: str | None,
        call_arguments: dict[str, dict],
    ) -> dict[str, Any]:
        """Run concurrency-safe calls with pool work overlapping inline work.

        Submit pool-backed tools first so their handles run in the
        background, then execute inline-backed tools, then collect the
        pool handles — a slow inline tool never stalls submitted pool work.
        """
        from .executor import ExecutionHandle

        raw_results: dict[str, Any] = {}
        pool_handles: list[tuple[Any, ExecutionHandle]] = []
        inline_calls: list[Any] = []

        inline_backends: dict[str, Any] = {}
        for tc in enabled_calls:
            tool_obj = self.get_tool(tc.name)
            backend = self._resolve_backend(
                tool_obj, execution_mode, default=self._execution_mode
            )
            if backend is self._inline_backend:
                inline_calls.append(tc)
                inline_backends[tc.id] = backend
                continue
            # Reuse the backend we just resolved instead of re-resolving.
            handle_or_error = self._submit_tool_call(
                tc, execution_mode, call_arguments, backend=backend
            )
            if isinstance(handle_or_error, _ToolError):
                raw_results[tc.id] = handle_or_error
            else:
                pool_handles.append((tc, handle_or_error))

        for tc in inline_calls:
            handle_or_error = self._submit_tool_call(
                tc, execution_mode, call_arguments, backend=inline_backends[tc.id]
            )
            if isinstance(handle_or_error, _ToolError):
                raw_results[tc.id] = handle_or_error
            else:
                raw_results[tc.id] = self._collect_handle_result(
                    handle_or_error, tc.name
                )

        for tc, handle in pool_handles:
            raw_results[tc.id] = self._collect_handle_result(handle, tc.name)

        return raw_results

    async def _aclassify_tool_calls(
        self,
        generic_tool_calls: list[Any],
        invocation_id: str | None = None,
    ) -> tuple[list[Any], dict[str, Any], dict[str, float], dict[str, dict]]:
        """Async twin of :meth:`_classify_tool_calls`.

        Uses :meth:`_acheck_tool_access` so async permission handlers are
        awaited natively instead of bridged through a thread pool.
        """
        enabled_calls: list[Any] = []
        tool_responses: dict[str, Any] = {}
        call_start_times: dict[str, float] = {}
        call_arguments: dict[str, dict] = {}

        for tc in generic_tool_calls:
            try:
                args = json.loads(tc.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}

            try:
                await self._acheck_tool_access(tc.name, args, invocation_id)
            except (KeyError, RuntimeError, PermissionError) as exc:
                tool_responses[tc.id] = _ToolError(
                    message=f"Error: {exc}",
                    exception_type=type(exc).__qualname__,
                )
            else:
                enabled_calls.append(tc)
                call_start_times[tc.id] = time.perf_counter()
                call_arguments[tc.id] = args

        return enabled_calls, tool_responses, call_start_times, call_arguments

    async def _aexecute_one(
        self,
        tc: Any,
        execution_mode: str | None,
        call_arguments: dict[str, dict],
    ) -> Any:
        """Execute one classified tool call asynchronously.

        Returns the finalized result (str/content-block list) on success
        or a :class:`_ToolError` on failure.  Inline-resolved tools are
        awaited directly on the caller's loop; pool-backed tools submit
        and await :meth:`ExecutionHandle.result_async`.
        """
        tool_obj = self.get_tool(tc.name)
        if tool_obj is None:
            return _ToolError(
                message=f"Error: Tool '{tc.name}' not found or callable is None",
            )

        clean_kwargs = self._clean_kwargs(call_arguments.get(tc.id, {}))
        per_call_timeout = tool_obj.metadata.timeout if tool_obj.metadata else None
        backend = self._resolve_backend(
            tool_obj, execution_mode, default=self._execution_mode
        )

        try:
            # Inline: pass tool.arun (async) so result_async can await.
            # Pool: pass tool.run (sync) for worker execution.
            # Bind tool_obj as default arg to avoid closure-over-loop.
            if backend is self._inline_backend:
                submit_fn = lambda _t=tool_obj, **kw: _t.arun(kw)  # noqa: E731
            else:
                submit_fn = lambda _t=tool_obj, **kw: _t.run(kw)  # noqa: E731
            handle = backend.submit(
                submit_fn,
                clean_kwargs,
                execution_id=tc.id,
                timeout=per_call_timeout,
            )
            raw = await handle.result_async()
            return self._finalize_result(raw, tc.name)
        except TimeoutError:
            return _ToolError(
                message=f"Error: Tool '{tc.name}' timed out",
                exception_type="TimeoutError",
                is_timeout=True,
            )
        except Exception as exc:
            return _ToolError(
                message=f"Error executing {tc.name}: {exc!s}",
                exception_type=type(exc).__qualname__,
                traceback_str=tb_module.format_exc(),
            )

    async def aexecute_tool_calls(
        self,
        tool_calls: list[Any],
        execution_mode: Literal["process", "thread"] | None = None,
    ) -> ResultList:
        """Async counterpart to :meth:`execute_tool_calls`.

        Runs concurrency-safe calls concurrently via ``asyncio.gather``
        over the per-tool async pipeline: inline tools (MCP/OpenAPI and
        async natives) overlap on the caller's loop, while pool-backed
        tools run off-loop and are awaited via ``result_async``.  If any
        tool is not concurrency-safe, all calls run sequentially.

        Args:
            tool_calls: Tool calls in any supported format.
            execution_mode: Optional backend override.

        Returns:
            A :class:`ResultList` in the same order as *tool_calls*.
        """
        from .utils import generate_invocation_id

        batch_inv_id = generate_invocation_id("bat")

        generic_tool_calls = convert_tool_calls(tool_calls)
        (
            enabled_calls,
            tool_responses,
            call_start_times,
            call_arguments,
        ) = await self._aclassify_tool_calls(generic_tool_calls, batch_inv_id)

        if not enabled_calls:
            return self._wrap_results(generic_tool_calls, tool_responses)

        has_unsafe = any(
            (tool_obj := self.get_tool(tc.name)) is not None
            and not tool_obj.metadata.is_concurrency_safe
            for tc in enabled_calls
        )

        if has_unsafe:
            raw_results = await self._aexecute_sequential(
                enabled_calls, execution_mode, call_arguments
            )
        else:
            raw_results = await self._aexecute_concurrent(
                enabled_calls, execution_mode, call_arguments
            )
        tool_responses.update(raw_results)

        self._log_tool_call_results(
            enabled_calls, raw_results, call_start_times, call_arguments, batch_inv_id
        )

        return self._wrap_results(generic_tool_calls, tool_responses)

    async def _aexecute_sequential(
        self,
        enabled_calls: list[Any],
        execution_mode: str | None,
        call_arguments: dict[str, dict],
    ) -> dict[str, Any]:
        """Await each call in order (used when an unsafe tool is present)."""
        raw_results: dict[str, Any] = {}
        for tc in enabled_calls:
            raw_results[tc.id] = await self._aexecute_one(
                tc, execution_mode, call_arguments
            )
        return raw_results

    async def _aexecute_concurrent(
        self,
        enabled_calls: list[Any],
        execution_mode: str | None,
        call_arguments: dict[str, dict],
    ) -> dict[str, Any]:
        """Run concurrency-safe calls concurrently via ``asyncio.gather``.

        Inline tools overlap on the caller's loop; pool-backed tools run
        off-loop and are awaited via ``result_async``.  ``_aexecute_one``
        catches ``Exception`` internally; ``gather(return_exceptions=True)``
        is a second layer that also captures anything that leaks (e.g.
        ``KeyboardInterrupt``).
        """
        import asyncio

        raw_results: dict[str, Any] = {}
        results = await asyncio.gather(
            *(
                self._aexecute_one(tc, execution_mode, call_arguments)
                for tc in enabled_calls
            ),
            return_exceptions=True,
        )
        for tc, result in zip(enabled_calls, results):
            if isinstance(result, BaseException):
                result = _ToolError(
                    message=f"Error executing {tc.name}: {result!s}",
                    exception_type=type(result).__qualname__,
                )
            raw_results[tc.id] = result
        return raw_results

    @staticmethod
    def _wrap_results(
        tool_calls: list[Any],
        tool_responses: dict[str, Any],
    ) -> ResultList:
        """Convert the internal responses dict into structured result objects."""
        items: list[ToolCallResult | ErrorResult] = []
        for tc in tool_calls:
            val = tool_responses.get(tc.id)
            if isinstance(val, _ToolError):
                items.append(val.to_error_result(tc))
            elif val is not None:
                items.append(ToolCallResult(id=tc.id, name=tc.name, result=val))
            else:
                items.append(
                    ErrorResult(id=tc.id, name=tc.name, message="No result produced")
                )
        return ResultList(items)

    def _log_tool_call_results(
        self,
        enabled_calls: list[Any],
        raw_results: dict[str, Any],
        call_start_times: dict[str, float],
        call_arguments: dict[str, dict],
        invocation_id: str | None = None,
    ) -> None:
        """Log execution results using :meth:`_log_tool_result`.

        Args:
            enabled_calls: List of tool calls that were executed.
            raw_results: Map of call ID to raw result (_ToolError or success value).
            call_start_times: Map of call ID to start timestamp.
            call_arguments: Map of call ID to parsed arguments.
            invocation_id: Invocation ID to attach to log entries.
        """
        end_time = time.perf_counter()
        for tc in enabled_calls:
            start_time = call_start_times.get(tc.id, end_time)
            duration_ms = (end_time - start_time) * 1000
            raw = raw_results.get(tc.id)
            kwargs = call_arguments.get(tc.id, {})

            if isinstance(raw, _ToolError):
                self._log_tool_result(
                    tc.name,
                    kwargs,
                    error=raw,
                    duration_ms=duration_ms,
                    invocation_id=invocation_id,
                )
            else:
                self._log_tool_result(
                    tc.name,
                    kwargs,
                    result=raw,
                    duration_ms=duration_ms,
                    invocation_id=invocation_id,
                )

    def build_tool_call_messages(
        self,
        tool_calls: list[Any],
        results: list[Any],
        api_format: API_FORMATS = "openai-chat",
    ) -> list[dict[str, Any]]:
        """Build conversation messages for a tool-calling round-trip.

        Combines the assistant message (tool call requests) and the tool
        result messages into the format required by the next LLM turn.

        Args:
            tool_calls: Tool call objects in any supported format
                (as received from the LLM).
            results: Structured results from :meth:`execute_tool_calls`.
            api_format: Target API format. Defaults to ``"openai-chat"``.

        Returns:
            Conversation messages ready to extend the message history.
            When multimodal content is present, an additional user
            message is appended containing the expanded content.
        """
        from .llm.tool_calls import _normalize_api_format
        from .llm.content_blocks import (
            build_multimodal_user_message,
            extract_multimodal_content,
        )

        api_format = _normalize_api_format(api_format)

        generic_tool_calls = convert_tool_calls(tool_calls)

        # Align IDs: results carry the IDs from execute_tool_calls,
        # but convert_tool_calls may regenerate them (e.g. Gemini).
        result_ids = [r.id for r in results]
        for i, tc in enumerate(generic_tool_calls):
            if i < len(result_ids):
                tc.id = result_ids[i]

        # Build response dict from structured results
        response_dict: dict[str, str | list] = {}
        for r in results:
            if isinstance(r, ErrorResult):
                response_dict[r.id] = str(r)
            else:
                response_dict[r.id] = r.result

        if api_format == "rosetta-ir":
            ir_calls = [tc.to_ir() for tc in generic_tool_calls]
            ir_results = [r.to_ir() for r in results]
            return [
                {"role": "assistant", "parts": ir_calls},
                {"role": "tool", "parts": ir_results},
            ]

        text_responses, extra_user_content = extract_multimodal_content(response_dict)

        messages: list[dict[str, Any]] = []
        messages.extend(
            build_assistant_messages(generic_tool_calls, api_format=api_format)
        )
        messages.extend(
            build_tool_result_messages(
                text_responses, api_format=api_format, tool_calls=generic_tool_calls
            )
        )

        if extra_user_content:
            messages.append(
                build_multimodal_user_message(extra_user_content, api_format)
            )

        return messages

    def recover_tool_call_assistant_message(
        self,
        tool_calls: list[Any],
        results: list[Any],
        api_format: API_FORMATS = "openai-chat",
    ) -> list[dict[str, Any]]:
        """Deprecated: use :meth:`build_tool_call_messages` instead."""
        warnings.warn(
            "recover_tool_call_assistant_message() is deprecated, "
            "use build_tool_call_messages() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.build_tool_call_messages(tool_calls, results, api_format)

    # ============== Presentation ==============
    def list_tools(self, include_disabled: bool = False) -> list[str]:
        """List registered tools.

        Args:
            include_disabled: If ``True``, include disabled tools in the
                result.  Defaults to ``False`` (only enabled tools).

        Returns:
            List[str]: A list of tool names.
        """
        if include_disabled:
            return list(self._tools.keys())
        return [n for n in self._tools if self.is_enabled(n)]

    def get_available_tools(self) -> list[str]:
        """Deprecated: use :meth:`list_tools` instead."""
        warnings.warn(
            "get_available_tools() is deprecated, use list_tools() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.list_tools()

    def list_all_tools(self) -> list[str]:
        """Deprecated: use ``list_tools(include_disabled=True)`` instead."""
        warnings.warn(
            "list_all_tools() is deprecated, "
            "use list_tools(include_disabled=True) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.list_tools(include_disabled=True)

    def get_tools_status(self) -> list[dict[str, Any]]:
        """Get status information for all registered tools.

        Returns a list of dictionaries containing status information for each
        tool, including enable/disable state, metadata summary, and tags.

        Returns:
            list[dict[str, Any]]: List of tool status dictionaries, each
                containing:

                - name (str): Tool name (with namespace prefix if applicable)
                - enabled (bool): Whether the tool is currently enabled
                - reason (str | None): Reason for disabling, if disabled
                - namespace (str | None): Namespace the tool belongs to
                - tags (list[str]): Sorted union of predefined and custom tags
                - locality (str): ``"local"``, ``"remote"``, or ``"any"``
                - is_async (bool): Whether the tool requires async execution
                - source (str): Origin of the tool (e.g. ``"native"``,
                  ``"mcp"``, ``"openapi"``, ``"langchain"``)
                - source_detail (str): Extra detail about the tool's origin
                  (e.g. transport URI, spec URL, class name)
                - think_augment (bool | None): Think-augmented calling setting
                - defer (bool): Whether the tool is deferred from initial prompt

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
                    "namespace": None,
                    "tags": [],
                    "locality": "any",
                    "is_async": False,
                    "think_augment": None,
                    "defer": False,
                }
            ]
        """
        status_list: list[dict[str, Any]] = []
        for tool_name, tool in self._tools.items():
            enabled = self.is_enabled(tool_name)
            reason = self.get_disable_reason(tool_name) if not enabled else None
            meta = tool.metadata
            status_list.append(
                {
                    "name": tool_name,
                    "enabled": enabled,
                    "reason": reason,
                    "namespace": tool.namespace,
                    "tags": sorted(meta.all_tags),
                    "locality": meta.locality,
                    "is_async": meta.is_async,
                    "source": meta.source,
                    "source_detail": meta.source_detail,
                    "think_augment": meta.think_augment,
                    "defer": meta.defer,
                }
            )
        return status_list

    def get_deferred_summaries(self) -> list[dict[str, str | None]]:
        """Get name and first-sentence description for deferred tools.

        Useful for injecting into system prompts so the LLM knows which
        additional tools are available via ``discover_tools``.

        Only enabled tools with ``ToolMetadata.defer=True`` are included.

        Returns:
            List of dicts with keys:

            - ``name`` (str): Tool name.
            - ``description`` (str): First sentence of the tool description.
            - ``namespace`` (str | None): Tool namespace, if any.
        """

        def _first_sentence(text: str) -> str:
            line = text.split("\n")[0].strip()
            dot = line.find(". ")
            return line[: dot + 1] if dot != -1 else line

        return [
            {
                "name": t.name,
                # Prefer search_hint as bullet description if set; it is
                # intentionally curated to be short.  Fall back to the
                # first sentence of the full description.
                "description": (
                    t.metadata.search_hint
                    if t.metadata and t.metadata.search_hint
                    else _first_sentence(t.description or "")
                ),
                "namespace": t.namespace,
            }
            for t in self._tools.values()
            if t.metadata and t.metadata.defer and self.is_enabled(t.name)
        ]

    def apply_metadata_config(self, overrides: "dict[str, Any]") -> None:
        """Apply ``tool_metadata`` overrides from a loaded ``ToolConfig``.

        Accepts ``dict[str, ToolMetadataOverride]`` (as returned by
        ``ToolConfig.tool_metadata``) or plain ``dict[str, dict]``.
        Silently skips tool names not present in the registry.

        Args:
            overrides: Mapping of exact tool name → metadata override.
                Each value must have ``search_hint`` (str) and optionally
                ``defer`` (bool | None) as attributes or dict keys.
        """
        for name, override in overrides.items():
            tool = self._tools.get(name)
            if tool is None:
                continue
            if isinstance(override, dict):
                hint = override.get("search_hint", "")
                defer = override.get("defer")
            else:
                hint = getattr(override, "search_hint", "")
                defer = getattr(override, "defer", None)
            if hint:
                tool.metadata.search_hint = hint
            if defer is not None:
                tool.metadata.defer = defer

    def get_schemas(
        self,
        tool_name: str | None = None,
        *,
        api_format: API_FORMATS = "openai-chat",
        tags: set[str | ToolTag] | None = None,
        exclude_tags: set[str | ToolTag] | None = None,
        sort: bool = True,
        include_deferred: bool = True,
    ) -> list[dict[str, Any]]:
        """Get tool definitions as JSON Schema dicts for a target API format.

        When no specific tool_name is given, only enabled tools are returned.
        Tools can be filtered by tags and sorted for deterministic ordering.

        Args:
            tool_name: Optional name of specific tool to get schema for.
                When set, tag filtering and sorting are skipped.
            api_format: Target API format. Defaults to ``"openai-chat"``.
            tags: If set, only include tools matching ANY of these tags.
            exclude_tags: Exclude tools matching ANY of these tags.
            sort: If True (default), sort tools by name for deterministic
                ordering. Stable sorting improves prompt cache hit rates.
            include_deferred: If False, exclude tools with
                ``metadata.defer == True``. Defaults to True for backward
                compatibility. Set to False when tool search is enabled so
                that deferred tools are only discovered via search.

        Returns:
            A list of tool definition dicts in the specified API format.
        """
        from .llm.tool_calls import _normalize_api_format

        api_format = _normalize_api_format(api_format)

        if tool_name:
            target_tool = self.get_tool(tool_name)
            tools = [target_tool] if target_tool else []
        else:
            # Only return enabled tools
            tools = [t for t in self._tools.values() if self.is_enabled(t.name)]

            # Defer filter
            if not include_deferred:
                tools = [t for t in tools if not t.metadata.defer]

            # Tag inclusion filter
            if tags is not None:
                include = {t.value if isinstance(t, ToolTag) else t for t in tags}
                tools = [t for t in tools if t.metadata.all_tags & include]

            # Tag exclusion filter
            if exclude_tags is not None:
                exclude = {
                    t.value if isinstance(t, ToolTag) else t for t in exclude_tags
                }
                tools = [t for t in tools if not (t.metadata.all_tags & exclude)]

            # Stable sort by name
            if sort:
                tools.sort(key=lambda t: t.name)

        schemas = []
        for tool in tools:
            # Resolve effective think_augment: per-tool overrides registry
            effective = tool.metadata.think_augment
            if effective is None:
                effective = self._think_augment
            schemas.append(tool.get_schema(api_format, _think_augment=effective))
        return schemas

    def get_tools_json(
        self,
        tool_name: str | None = None,
        *,
        api_format: API_FORMATS = "openai-chat",
        tags: set[str | ToolTag] | None = None,
        exclude_tags: set[str | ToolTag] | None = None,
        sort: bool = True,
        include_deferred: bool = True,
    ) -> list[dict[str, Any]]:
        """Deprecated: use :meth:`get_schemas` instead."""
        warnings.warn(
            "get_tools_json() is deprecated, use get_schemas() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.get_schemas(
            tool_name,
            api_format=api_format,
            tags=tags,
            exclude_tags=exclude_tags,
            sort=sort,
            include_deferred=include_deferred,
        )
