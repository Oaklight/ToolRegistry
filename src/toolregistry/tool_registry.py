import asyncio
import json
import logging
import random
import string
import time
import warnings
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

from ._admin import AdminMixin
from ._callbacks import ChangeCallbackMixin
from ._enable_disable import EnableDisableMixin
from ._logging import ExecutionLoggingMixin
from ._namespace import NamespaceMixin
from ._permissions import PermissionsMixin
from ._registration import RegistrationMixin

logger = logging.getLogger(__name__)


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
                When ``True``, a ``thought`` property is included in
                every tool's schema so LLMs can emit chain-of-thought
                reasoning alongside tool calls.  Individual tools can
                override this via ``ToolMetadata.think_augment``.
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

        When enabled, a ``thought`` property is included in every tool's
        schema (via :meth:`get_schemas`) so that LLMs can emit
        chain-of-thought reasoning alongside tool calls.  Individual
        tools can still override this via ``ToolMetadata.think_augment``.

        Reference: https://arxiv.org/abs/2601.18282
        """
        self._think_augment = True

    def disable_think_augment(self) -> None:
        """Disable thought-augmented tool calling globally.

        When disabled, the ``thought`` property is stripped from tool
        schemas produced by :meth:`get_schemas`, unless a tool explicitly
        opts in via ``ToolMetadata.think_augment = True``.
        """
        self._think_augment = False

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

    def set_execution_mode(self, mode: Literal["thread", "process"]) -> None:
        """Set the execution mode for parallel tasks.

        Args:
            mode (Literal["thread", "process"]): The desired execution mode.

        Raises:
            ValueError: If an invalid mode is provided.
        """
        if mode not in {"thread", "process"}:
            raise ValueError("Invalid mode. Choose 'thread' or 'process'.")
        self._execution_mode = mode

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
        from .admin import ExecutionLogEntry, ExecutionStatus
        from .executor import ExecutionHandle

        generic_tool_calls = convert_tool_calls(tool_calls)

        # Separate enabled and disabled tool calls
        enabled_calls = []
        tool_responses: dict[str, str | list] = {}
        # Track timing for each tool call
        call_start_times: dict[str, float] = {}
        call_arguments: dict[str, dict] = {}

        for tc in generic_tool_calls:
            if not self.is_enabled(tc.name):
                reason = self.get_disable_reason(tc.name) or "Tool is disabled"
                tool_responses[tc.id] = (
                    f"Error: Tool '{tc.name}' is disabled. Reason: {reason}"
                )
                # Log disabled tool call
                if self._execution_log is not None:
                    try:
                        args = json.loads(tc.arguments)
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    entry = ExecutionLogEntry.create(
                        tool_name=tc.name,
                        status=ExecutionStatus.DISABLED,
                        duration_ms=0.0,
                        arguments=args,
                        error=f"Tool is disabled. Reason: {reason}",
                    )
                    self._execution_log.add(entry)
            else:
                # Parse arguments early for permission check
                try:
                    args = json.loads(tc.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}

                # Evaluate permission policy
                tool_obj = self.get_tool(tc.name)
                if tool_obj is not None:
                    decision = self._resolve_permission(tool_obj, args)
                else:
                    decision = PermissionResult.ALLOW

                if decision == PermissionResult.DENY:
                    tool_responses[tc.id] = (
                        f"Error: Tool '{tc.name}' denied by permission policy."
                    )
                    if self._execution_log is not None:
                        entry = ExecutionLogEntry.create(
                            tool_name=tc.name,
                            status=ExecutionStatus.ERROR,
                            duration_ms=0.0,
                            arguments=args,
                            error="Denied by permission policy",
                        )
                        self._execution_log.add(entry)
                else:
                    enabled_calls.append(tc)
                    call_start_times[tc.id] = time.perf_counter()
                    call_arguments[tc.id] = args

        # Execute only enabled tool calls
        if enabled_calls:
            mode = execution_mode or self._execution_mode
            backend = (
                self._thread_backend if mode == "thread" else self._process_backend
            )

            # Check if any tool is not concurrency-safe
            has_unsafe = any(
                (tool_obj := self.get_tool(tc.name)) is not None
                and not tool_obj.metadata.is_concurrency_safe
                for tc in enabled_calls
            )

            handles: list[tuple[Any, ExecutionHandle]] = []

            for tc in enabled_calls:
                function_name = tc.name
                function_args = call_arguments.get(tc.id, {})
                tool_obj = self.get_tool(function_name)
                if tool_obj and not tool_obj._has_native_thought_param():
                    function_args.pop("thought", None)
                callable_func = tool_obj.callable if tool_obj else None

                if callable_func is None:
                    tool_responses[tc.id] = (
                        f"Error: Tool '{function_name}' not found or callable is None"
                    )
                    continue

                per_call_timeout = (
                    tool_obj.metadata.timeout
                    if tool_obj and tool_obj.metadata
                    else None
                )

                try:
                    handle = backend.submit(
                        callable_func,
                        function_args,
                        execution_id=tc.id,
                        timeout=per_call_timeout,
                    )
                except Exception as e:
                    # Fallback to thread backend on process serialization error
                    if mode == "process":
                        try:
                            handle = self._thread_backend.submit(
                                callable_func,
                                function_args,
                                execution_id=tc.id,
                                timeout=per_call_timeout,
                            )
                        except Exception as e2:
                            tool_responses[tc.id] = (
                                f"Error preparing tool call {function_name}: {e2!s}"
                            )
                            continue
                    else:
                        tool_responses[tc.id] = (
                            f"Error preparing tool call {function_name}: {e!s}"
                        )
                        continue

                if has_unsafe:
                    # Sequential execution: wait for result immediately
                    try:
                        result = handle.result()
                        tool_responses[tc.id] = self._finalize_result(
                            result, function_name
                        )
                    except TimeoutError:
                        tool_responses[tc.id] = (
                            f"Error: Tool '{function_name}' timed out"
                        )
                    except Exception as e:
                        tool_responses[tc.id] = (
                            f"Error executing {function_name}: {e!s}"
                        )
                else:
                    handles.append((tc, handle))

            # Collect results from parallel handles
            for tc, handle in handles:
                try:
                    result = handle.result()
                    tool_responses[tc.id] = self._finalize_result(result, tc.name)
                except TimeoutError:
                    tool_responses[tc.id] = f"Error: Tool '{tc.name}' timed out"
                except Exception as e:
                    tool_responses[tc.id] = f"Error executing {tc.name}: {e!s}"

            # Log executed tool calls
            if self._execution_log is not None:
                end_time = time.perf_counter()
                for tc in enabled_calls:
                    start_time = call_start_times.get(tc.id, end_time)
                    duration_ms = (end_time - start_time) * 1000
                    response = tool_responses.get(tc.id, "")
                    response_str = str(response)
                    is_error = response_str.startswith("Error")

                    entry = ExecutionLogEntry.create(
                        tool_name=tc.name,
                        status=ExecutionStatus.ERROR
                        if is_error
                        else ExecutionStatus.SUCCESS,
                        duration_ms=duration_ms,
                        arguments=call_arguments.get(tc.id, {}),
                        result=None if is_error else response_str,
                        error=response_str if is_error else None,
                    )
                    self._execution_log.add(entry)

        return tool_responses

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

    def get_schemas(
        self,
        tool_name: str | None = None,
        *,
        api_format: API_FORMATS = "openai-chat",
        tags: set[str | ToolTag] | None = None,
        exclude_tags: set[str | ToolTag] | None = None,
        sort: bool = True,
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
            schemas.append(tool.get_json_schema(api_format, _think_augment=effective))
        return schemas

    def get_tools_json(
        self,
        tool_name: str | None = None,
        *,
        api_format: API_FORMATS = "openai-chat",
        tags: set[str | ToolTag] | None = None,
        exclude_tags: set[str | ToolTag] | None = None,
        sort: bool = True,
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
        )
