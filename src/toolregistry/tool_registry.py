import asyncio
import json
import logging
import random
import string
import time
from typing import Any, Literal
from collections.abc import Callable

from .executor import ProcessPoolBackend, ThreadBackend
from .tool import ToolTag
from .permissions import (
    PermissionResult,
)
from .types import (
    API_FORMATS,
    AnyToolCall,
    convert_tool_calls,
    recover_assistant_message,
    recover_tool_message,
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
        super().__init__()
        if name is None:
            name = f"reg_{''.join(random.sample(string.hexdigits.lower(), 4))}"
        self.name = name
        self._thread_backend = ThreadBackend()
        self._process_backend = ProcessPoolBackend()
        self._execution_mode: Literal["process", "thread"] = "process"

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

    # ============== Execution ==============
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
    ) -> dict[str, str]:
        """Execute tool calls with concurrency using cloudpickle for serialization.

        Disabled tools are rejected with an error message instead of being
        executed. If logging is enabled, execution details are recorded.

        Args:
            tool_calls: List of tool calls to be executed in any supported format.
            execution_mode: Execution mode to use; defaults to the Executor's current mode.

        Returns:
            Dict[str, str]: Dictionary mapping tool call IDs to their results.
        """
        from .admin import ExecutionLogEntry, ExecutionStatus
        from .executor import ExecutionHandle

        generic_tool_calls = convert_tool_calls(tool_calls)

        # Separate enabled and disabled tool calls
        enabled_calls = []
        tool_responses: dict[str, str] = {}
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
                        try:
                            json.dumps(result)
                        except (TypeError, ValueError):
                            result = str(result)
                        tool_responses[tc.id] = (
                            result if isinstance(result, str) else json.dumps(result)
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
                    try:
                        json.dumps(result)
                    except (TypeError, ValueError):
                        result = str(result)
                    tool_responses[tc.id] = (
                        result if isinstance(result, str) else json.dumps(result)
                    )
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
        messages.extend(
            recover_tool_message(
                tool_responses, api_format=api_format, tool_calls=generic_tool_calls
            )
        )
        return messages

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
        tags: set[str | ToolTag] | None = None,
        exclude_tags: set[str | ToolTag] | None = None,
        sort: bool = True,
    ) -> list[dict[str, Any]]:
        """Get the JSON representation of registered tools, following JSON Schema.

        When no specific tool_name is given, only enabled tools are returned.
        Tools can be filtered by tags and sorted for deterministic ordering.

        Args:
            tool_name: Optional name of specific tool to get schema for.
                When set, tag filtering and sorting are skipped.
            api_format: API format for the schema output.
            tags: If set, only include tools matching ANY of these tags.
            exclude_tags: Exclude tools matching ANY of these tags.
            sort: If True (default), sort tools by name for deterministic
                ordering. Stable sorting improves prompt cache hit rates.

        Returns:
            A list of tools in JSON format, compliant with JSON Schema.
        """
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

        return [tool.get_json_schema(api_format) for tool in tools]
