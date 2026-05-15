import asyncio
import json
import logging
import random
import string
import time
import traceback as tb_module
import warnings
from dataclasses import dataclass
from typing import Any, Literal
from collections.abc import Callable

from .executor import ProcessPoolBackend, ThreadBackend
from .tool import ToolTag
from .truncation import truncate_result
from .types.content_blocks import is_content_block_list
from .permissions import (
    PermissionResult,
)
from .types import (
    API_FORMATS,
    AnyToolCall,
    build_assistant_message,
    build_tool_response,
    convert_tool_calls,
)

from .events import ChangeCallback, ChangeEvent, ChangeEventType
from .tool_discovery import TOOL_DISCOVERY_NAME, ToolDiscoveryTool

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
        self._execution_mode: Literal["process", "thread"] = "process"
        self._default_max_result_size = default_max_result_size
        self._think_augment = think_augment
        self._tool_discovery: ToolDiscoveryTool | None = None
        self._tool_discovery_callback: ChangeCallback | None = None

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
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.close_async())
        finally:
            loop.close()

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
            description=(
                "Discover registered tools by exact name or natural "
                "language query. Use this to inspect a specific tool "
                "by name (returns full schema) or to search for "
                "relevant tools when you need a capability not "
                "visible in your current tool list."
            ),
            metadata=ToolMetadata(defer=False),
        )
        self.register(discovery_tool)

        def _on_registry_change(event: ChangeEvent) -> None:
            if event.event_type in {
                ChangeEventType.REGISTER,
                ChangeEventType.UNREGISTER,
            }:
                if event.tool_name != TOOL_DISCOVERY_NAME:
                    discoverer.rebuild_index()

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

    # ============== Execution ==============
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
    ) -> tuple[list[Any], dict[str, str | list], dict[str, float], dict[str, dict]]:
        """Separate tool calls into enabled vs disabled/denied, logging rejections.

        Args:
            generic_tool_calls: Normalized tool call list.

        Returns:
            Tuple of (enabled_calls, tool_responses, call_start_times, call_arguments).
        """
        from .admin import ExecutionStatus

        enabled_calls: list[Any] = []
        tool_responses: dict[str, str | list] = {}
        call_start_times: dict[str, float] = {}
        call_arguments: dict[str, dict] = {}

        for tc in generic_tool_calls:
            if not self.is_enabled(tc.name):
                reason = self.get_disable_reason(tc.name) or "Tool is disabled"
                tool_responses[tc.id] = (
                    f"Error: Tool '{tc.name}' is disabled. Reason: {reason}"
                )
                self._log_entry(
                    tc.name,
                    ExecutionStatus.DISABLED,
                    0.0,
                    {},
                    error=f"Tool is disabled. Reason: {reason}",
                )
                continue

            try:
                args = json.loads(tc.arguments)
            except (json.JSONDecodeError, TypeError):
                args = {}

            tool_obj = self.get_tool(tc.name)
            decision = (
                self._resolve_permission(tool_obj, args)
                if tool_obj is not None
                else PermissionResult.ALLOW
            )

            if decision == PermissionResult.DENY:
                tool_responses[tc.id] = (
                    f"Error: Tool '{tc.name}' denied by permission policy."
                )
                self._log_entry(
                    tc.name,
                    ExecutionStatus.ERROR,
                    0.0,
                    args,
                    error="Denied by permission policy",
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
        )
        self._execution_log.add(entry)

    def _submit_tool_call(
        self,
        tc: Any,
        backend: Any,
        call_arguments: dict[str, dict],
        mode: str,
    ) -> Any | _ToolError:
        """Submit a single tool call for execution.

        Args:
            tc: The tool call to submit.
            backend: Execution backend (process or thread).
            call_arguments: Map of call ID to parsed arguments.
            mode: Current execution mode ("process" or "thread").

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

        try:
            return backend.submit(
                callable_func,
                function_args,
                execution_id=tc.id,
                timeout=per_call_timeout,
            )
        except Exception as e:
            if mode == "process":
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
        tool_calls: list[AnyToolCall],
        execution_mode: Literal["process", "thread"] | None = None,
    ) -> dict[str, str | list]:
        """Execute tool calls with concurrency using cloudpickle for serialization.

        Disabled tools are rejected with an error message instead of being
        executed. If logging is enabled, execution details are recorded.

        Args:
            tool_calls: List of tool calls to be executed in any supported format.
            execution_mode: Execution mode to use; defaults to the Executor's current mode.

        Returns:
            Dictionary mapping tool call IDs to their results.  Values
            are ``str`` for normal results or ``list[ContentBlock]`` for
            multimodal results (e.g. images).
        """
        from .executor import ExecutionHandle

        generic_tool_calls = convert_tool_calls(tool_calls)
        enabled_calls, tool_responses, call_start_times, call_arguments = (
            self._classify_tool_calls(generic_tool_calls)
        )

        if not enabled_calls:
            return tool_responses

        mode = execution_mode or self._execution_mode
        backend = self._thread_backend if mode == "thread" else self._process_backend

        has_unsafe = any(
            (tool_obj := self.get_tool(tc.name)) is not None
            and not tool_obj.metadata.is_concurrency_safe
            for tc in enabled_calls
        )

        handles: list[tuple[Any, ExecutionHandle]] = []
        # Map call ID → raw result (_ToolError or success value)
        raw_results: dict[str, Any] = {}

        for tc in enabled_calls:
            handle_or_error = self._submit_tool_call(tc, backend, call_arguments, mode)
            if isinstance(handle_or_error, _ToolError):
                raw_results[tc.id] = handle_or_error
                tool_responses[tc.id] = handle_or_error.message
                continue

            if has_unsafe:
                result = self._collect_handle_result(handle_or_error, tc.name)
                raw_results[tc.id] = result
                tool_responses[tc.id] = (
                    result.message if isinstance(result, _ToolError) else result
                )
            else:
                handles.append((tc, handle_or_error))

        for tc, handle in handles:
            result = self._collect_handle_result(handle, tc.name)
            raw_results[tc.id] = result
            tool_responses[tc.id] = (
                result.message if isinstance(result, _ToolError) else result
            )

        # Log executed tool calls and emit error events
        self._log_tool_call_results(
            enabled_calls, raw_results, call_start_times, call_arguments
        )

        return tool_responses

    def _log_tool_call_results(
        self,
        enabled_calls: list[Any],
        raw_results: dict[str, Any],
        call_start_times: dict[str, float],
        call_arguments: dict[str, dict],
    ) -> None:
        """Log execution results and emit error events for completed tool calls.

        Args:
            enabled_calls: List of tool calls that were executed.
            raw_results: Map of call ID to raw result (_ToolError or success value).
            call_start_times: Map of call ID to start timestamp.
            call_arguments: Map of call ID to parsed arguments.
        """
        from .admin import ExecutionStatus

        end_time = time.perf_counter()
        for tc in enabled_calls:
            start_time = call_start_times.get(tc.id, end_time)
            duration_ms = (end_time - start_time) * 1000
            raw = raw_results.get(tc.id)

            if isinstance(raw, _ToolError):
                status = (
                    ExecutionStatus.TIMEOUT if raw.is_timeout else ExecutionStatus.ERROR
                )
                self._log_entry(
                    tc.name,
                    status,
                    duration_ms,
                    call_arguments.get(tc.id, {}),
                    error=raw.message,
                    exception_type=raw.exception_type,
                    traceback=raw.traceback_str,
                )
                self._emit_change(
                    ChangeEvent(
                        event_type=ChangeEventType.TOOL_ERROR,
                        tool_name=tc.name,
                        reason=raw.message,
                        metadata={
                            "exception_type": raw.exception_type,
                            "arguments": call_arguments.get(tc.id, {}),
                        },
                    )
                )
            else:
                self._log_entry(
                    tc.name,
                    ExecutionStatus.SUCCESS,
                    duration_ms,
                    call_arguments.get(tc.id, {}),
                    result=str(raw) if raw is not None else None,
                )

    def build_tool_call_messages(
        self,
        tool_calls: list[AnyToolCall],
        tool_responses: dict[str, str | list],
        api_format: API_FORMATS = "openai-chat",
    ) -> list[dict[str, Any]]:
        """Build conversation messages for a tool-calling round-trip.

        Combines the assistant message (tool call requests) and the tool
        result messages into the format required by the next LLM turn.

        This is a convenience method wrapping :func:`build_assistant_message`
        and :func:`build_tool_response`.  It handles Gemini-specific ID
        alignment automatically (position-based remapping).

        .. important::

            Do **not** reorder ``tool_calls`` between
            :meth:`execute_tool_calls` and this method.  Gemini format
            relies on positional alignment between ``tool_calls`` and
            ``tool_responses`` because Gemini does not provide tool call
            IDs upstream.

        Args:
            tool_calls: Tool call objects in any supported format.
            tool_responses: Mapping of tool call IDs to results,
                as returned by :meth:`execute_tool_calls`.  Values are
                ``str`` or ``list[ContentBlock]`` for multimodal results.
            api_format: Target API format. Defaults to ``"openai-chat"``.

        Returns:
            Conversation messages ready to extend the message history.
            When multimodal content is present, an additional user
            message is appended containing the expanded content.
        """
        from .types.common import _normalize_api_format
        from .types.content_blocks import (
            build_expanded_user_message,
            expand_content_blocks,
        )

        api_format = _normalize_api_format(api_format)

        messages = []
        generic_tool_calls = convert_tool_calls(tool_calls)

        # Align IDs: convert_tool_calls may generate new IDs (e.g. Gemini
        # format has no upstream ID), but tool_responses already carries
        # the IDs produced by execute_tool_calls.  Remap by position so
        # the assistant and tool messages reference the same IDs.
        response_ids = list(tool_responses.keys())
        for i, tc in enumerate(generic_tool_calls):
            if i < len(response_ids):
                tc.id = response_ids[i]

        # Expand multimodal content blocks into a separate user message
        text_responses, extra_user_content = expand_content_blocks(tool_responses)

        messages.extend(
            build_assistant_message(generic_tool_calls, api_format=api_format)
        )
        messages.extend(
            build_tool_response(
                text_responses, api_format=api_format, tool_calls=generic_tool_calls
            )
        )

        if extra_user_content:
            messages.append(build_expanded_user_message(extra_user_content, api_format))

        return messages

    def recover_tool_call_assistant_message(
        self,
        tool_calls: list[AnyToolCall],
        tool_responses: dict[str, str | list],
        api_format: API_FORMATS = "openai-chat",
    ) -> list[dict[str, Any]]:
        """Deprecated: use :meth:`build_tool_call_messages` instead."""
        warnings.warn(
            "recover_tool_call_assistant_message() is deprecated, "
            "use build_tool_call_messages() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.build_tool_call_messages(tool_calls, tool_responses, api_format)

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
                "description": _first_sentence(t.description or ""),
                "namespace": t.namespace,
            }
            for t in self._tools.values()
            if t.metadata and t.metadata.defer and self.is_enabled(t.name)
        ]

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
        from .types.common import _normalize_api_format

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
