import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.types import (
    BlobResourceContents,
    EmbeddedResource,
    ImageContent,
    Implementation,
    TextContent,
    TextResourceContents,
)
from mcp.types import Tool as ToolSpec

from ..._vendor.structlog import get_logger
from ._compat import get_field
from ...events import ChangeEvent, ChangeEventType, RefreshResult
from ...tool import Tool, ToolMetadata
from ...tool_registry import ToolRegistry
from ...tool_wrapper import BaseToolWrapper
from ...utils import normalize_tool_name
from .client import MCPClient
from .connection import MCPConnectionManager

logger = get_logger()


class MCPToolWrapper(BaseToolWrapper):
    """Wrapper class providing both async and sync versions of MCP tool calls.

    Attributes:
        name (str): Name of the tool/operation.
        params (Optional[List[str]]): List of parameter names.
    """

    def __init__(
        self,
        connection: MCPConnectionManager,
        name: str,
        params: list[str] | None,
    ) -> None:
        """Initialize MCP tool wrapper.

        Args:
            connection: Shared connection manager for the MCP server.
            name (str): Name of the tool/operation.
            params (Optional[List[str]]): List of parameter names.
        """
        super().__init__(name=name, params=params)
        self._connection = connection

    @property
    def transport(self) -> str | dict | Path:
        """Transport source, for backward compatibility."""
        return self._connection.transport

    def _validate_and_extract(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Validate name and extract parameters from args/kwargs.

        Shared by both ``call_sync`` and ``call_async`` to ensure
        identical parameter handling.
        """
        if not self.name:
            raise ValueError("Tool name must be set before calling")
        kwargs = self._process_args(*args, **kwargs)
        validated: dict[str, Any] = {}
        if self.params:
            for param_name in self.params:
                if param_name in kwargs:
                    validated[param_name] = kwargs[param_name]
        return validated

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous implementation of MCP tool call.

        Delegates to the connection manager's ``call_tool_sync`` which
        runs the coroutine on a persistent background event loop,
        keeping the MCP transport alive across calls.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ValueError: If name not set.
            Exception: If tool execution fails.
        """
        try:
            validated_params = self._validate_and_extract(*args, **kwargs)
            result = self._connection.call_tool_sync(self.name, validated_params)
            return self._post_process_result(result)
        except Exception:
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Async implementation of MCP tool call.

        Args:
            args (Any): Positional arguments to pass to the tool.
            kwargs (Any): Keyword arguments to pass to the tool.

        Returns:
            Any: Result from tool execution.

        Raises:
            ValueError: If name not set.
            Exception: If tool execution fails.
        """
        try:
            validated_params = self._validate_and_extract(*args, **kwargs)
            result = await self._connection.call_tool(self.name, validated_params)
            return self._post_process_result(result)
        except Exception:
            import traceback

            logger.error(
                f"Original Exception happens at {self.name}:\n{traceback.format_exc()}"
            )
            raise

    def _post_process_result(self, result: Any) -> Any:
        """Post-process the result from an MCP tool call.

        Returns canonical content block format when the result contains
        non-text content (images, blobs).  Single text-only results are
        returned as plain strings for backward compatibility.

        Args:
            result: Raw result from MCP tool call.

        Returns:
            A plain ``str`` for text-only results, or a
            ``list[ContentBlock]`` for multimodal results.

        Raises:
            NotImplementedError: If content type is not supported.
        """
        if isinstance(result, list):
            contents = result
        else:
            is_error = get_field(result, "is_error", "isError", False)
            if is_error or not result.content:
                return result
            contents = result.content

        _IMAGE_MIME_PREFIXES = ("image/",)

        def process_text(content: TextContent) -> dict:
            return {"type": "text", "text": content.text}

        def process_image(content: ImageContent) -> dict:
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": get_field(content, "mime_type", "mimeType"),
                    "data": content.data,
                },
            }

        def process_embedded(content: EmbeddedResource) -> dict:
            if isinstance(content.resource, TextResourceContents):
                return {"type": "text", "text": content.resource.text}
            elif isinstance(content.resource, BlobResourceContents):
                mime = get_field(content.resource, "mime_type", "mimeType") or ""
                if mime.startswith(_IMAGE_MIME_PREFIXES):
                    return {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": content.resource.blob,
                        },
                    }
                return {
                    "type": "text",
                    "text": f"[Blob: {mime}, {len(content.resource.blob)} chars]",
                }
            return {"type": "text", "text": str(content)}

        handlers: dict[Any, Callable] = {
            TextContent: process_text,
            ImageContent: process_image,
            EmbeddedResource: process_embedded,
        }

        processed = []
        for content in contents:
            content_type = type(content)
            handler = handlers.get(content_type)
            if handler is None:
                raise NotImplementedError(
                    f"No handler for content type: {content_type}"
                )
            processed.append(handler(content))

        # Single text-only result: return plain string for backward compat
        if len(processed) == 1 and processed[0].get("type") == "text":
            return processed[0]["text"]

        return processed


class MCPTool(Tool):
    """Wrapper class for MCP tools that preserves original function metadata.

    Attributes:
        name (str): Name of the tool.
        description (str): Description of the tool.
        parameters (Dict[str, Any]): Parameter schema definition.
        callable (Callable[..., Any]): The wrapped callable function.
        is_async (bool): Whether the tool is async, defaults to False.
    """

    @classmethod
    def from_tool_json(
        cls,
        tool_spec: ToolSpec,
        connection: MCPConnectionManager,
        namespace: str | None = None,
    ) -> "MCPTool":
        """Create an MCPTool instance from a JSON representation.

        Args:
            tool_spec (ToolSpec): The JSON representation of the tool.
            connection: Shared connection manager for the MCP server.
            namespace (Optional[str]): An optional namespace to prefix the tool name.
                If provided, the tool name will be formatted as "{namespace}.{name}".

        Returns:
            MCPTool: A new instance of MCPTool configured with the provided parameters.
        """
        name = tool_spec.name
        description = tool_spec.description or ""
        input_schema = get_field(tool_spec, "input_schema", "inputSchema", {})
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            input_schema = {"type": "object", "properties": {}}
        else:
            properties = input_schema.get("properties")
            if not isinstance(properties, dict):
                properties = {}
            input_schema["properties"] = properties

        wrapper = MCPToolWrapper(
            connection=connection,
            name=name,
            params=list(input_schema["properties"].keys()),
        )

        # Build a human-readable source_detail from the transport config.
        transport = connection.transport
        if isinstance(transport, dict):
            cmd = transport.get("command", "")
            args = " ".join(transport.get("args", []))
            source_detail = f"stdio:{cmd} {args}".strip()
        else:
            source_detail = str(transport)

        tool = cls(
            name=normalize_tool_name(name),
            description=description,
            parameters=input_schema,
            callable=wrapper,
            metadata=ToolMetadata(
                is_async=False,
                source="mcp",
                source_detail=source_detail,
                natural_backend="inline",
            ),
        )

        if namespace:
            tool.update_namespace(namespace)

        return tool


class MCPIntegration:
    """Handles integration with MCP server for tool registration.

    Attributes:
        registry (ToolRegistry): Tool registry instance.
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._connections: list[MCPConnectionManager] = []
        self._registered_tool_names: set[str] = set()
        self._transport: str | dict[str, Any] | Path | None = None
        self._resolved_ns: str | None = None
        self._persistent: bool = True
        self._headers: dict[str, str] | None = None
        self._refresh_lock = threading.Lock()
        self._poll_timer: threading.Timer | None = None
        self._poll_interval: float | None = None

    async def register_mcp_tools_async(
        self,
        transport: str | dict[str, Any] | Path,
        namespace: bool | str = False,
        persistent: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Async implementation to register all tools from an MCP server.

        Args:
            transport: MCP server transport — URL string, script path, or
                stdio dict with ``command``, ``args``, ``env`` keys.
            namespace: Whether to prefix tool names with a namespace.
                ``False`` (default) means no namespace, ``True`` derives it
                from the server info, or pass a string directly.
            persistent: If True (default), keep the connection open across
                tool calls.
            headers: HTTP headers for SSE or streamable-http transports.

        Raises:
            RuntimeError: If connection to server fails.
        """
        self._transport = transport
        self._persistent = persistent
        self._headers = headers

        connection = MCPConnectionManager(
            transport=transport,
            persistent=persistent,
            headers=headers,
        )
        self._connections.append(connection)

        async with MCPClient(transport, headers=headers) as client:
            server_info: Implementation | None = client.server_info

            if isinstance(namespace, str):
                resolved_ns = namespace
            elif namespace:
                resolved_ns = server_info.name if server_info else "MCP sse service"
            else:
                resolved_ns = None
            self._resolved_ns = resolved_ns

            tools_response: list[ToolSpec] = await client.list_tools()

            for tool_spec in tools_response:
                mcp_tool = MCPTool.from_tool_json(
                    tool_spec=tool_spec,
                    connection=connection,
                    namespace=resolved_ns,
                )
                self.registry.register(mcp_tool, namespace=resolved_ns)
                self._registered_tool_names.add(mcp_tool.name)

    def register_mcp_tools(
        self,
        transport: str | dict[str, Any] | Path,
        namespace: bool | str = False,
        persistent: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Register all tools from an MCP server (synchronous entry point).

        Args:
            transport: MCP server transport — URL string, script path, or
                stdio dict with ``command``, ``args``, ``env`` keys.
            namespace: Whether to prefix tool names with a namespace.
            persistent: If True (default), keep the connection open across
                tool calls.
            headers: HTTP headers for SSE or streamable-http transports.
        """
        from ..._async_runtime import AsyncRuntime

        AsyncRuntime.run_sync(
            self.register_mcp_tools_async(
                transport, namespace, persistent, headers=headers
            )
        )

    # ---- Refresh ----

    async def refresh_async(self) -> RefreshResult:
        """Re-list tools from the MCP server and synchronise the registry.

        Opens a temporary client connection to call ``list_tools()``,
        compares with the currently registered set, and applies additions,
        removals, and updates.

        Returns:
            A :class:`RefreshResult` describing what changed.

        Raises:
            ValueError: If transport was not stored (should not happen
                after a successful registration).
        """
        if self._transport is None:
            raise ValueError("Cannot refresh: no transport configured.")

        if not self._connections:
            raise ValueError("Cannot refresh: no connection available.")
        connection = self._connections[0]

        # Build source_detail for the result
        transport = self._transport
        if isinstance(transport, dict):
            cmd = transport.get("command", "")
            args = " ".join(transport.get("args", []))
            source_detail = f"stdio:{cmd} {args}".strip()
        else:
            source_detail = str(transport)

        async with MCPClient(self._transport, headers=self._headers) as client:
            tools_response: list[ToolSpec] = await client.list_tools()

        sep = getattr(self.registry, "_name_sep", "-")

        # Build candidate tools from the fresh response
        new_tools: dict[str, MCPTool] = {}
        for tool_spec in tools_response:
            candidate = MCPTool.from_tool_json(
                tool_spec=tool_spec,
                connection=connection,
                namespace=self._resolved_ns,
            )
            candidate.update_namespace(self._resolved_ns, force=True, sep=sep)
            new_tools[candidate.name] = candidate

        old_names = set(self._registered_tool_names)
        new_names = set(new_tools.keys())

        # Snapshot disabled state
        disabled_snapshot: dict[str, str] = {}
        for name in old_names:
            if not self.registry.is_enabled(name):
                disabled_snapshot[name] = self.registry.get_disable_reason(name) or ""

        to_remove = old_names - new_names
        to_add = new_names - old_names
        maybe_updated = old_names & new_names

        added: list[str] = []
        removed: list[str] = []
        updated: list[str] = []
        unchanged = 0

        for name in to_remove:
            self.registry._unregister(name)
            removed.append(name)

        for name in to_add:
            self.registry.register(new_tools[name], namespace=self._resolved_ns)
            added.append(name)

        for name in maybe_updated:
            candidate = new_tools[name]
            existing = self.registry._tools.get(name)
            if existing and (
                existing.parameters != candidate.parameters
                or existing.description != candidate.description
            ):
                self.registry._tools[name] = candidate
                self.registry._emit_change(
                    ChangeEvent(
                        event_type=ChangeEventType.REFRESH,
                        tool_name=name,
                    )
                )
                updated.append(name)
            else:
                unchanged += 1

        # Restore disabled state for surviving tools
        for name, reason in disabled_snapshot.items():
            if name in new_names:
                self.registry.disable(name, reason)

        self._registered_tool_names = new_names

        return RefreshResult(
            source="mcp",
            source_detail=source_detail,
            added=tuple(added),
            removed=tuple(removed),
            updated=tuple(updated),
            unchanged=unchanged,
        )

    def refresh(self) -> RefreshResult:
        """Synchronous version of :meth:`refresh_async`."""
        from ..._async_runtime import AsyncRuntime

        with self._refresh_lock:
            return AsyncRuntime.run_sync(self.refresh_async())

    # ---- Background polling ----

    def start_polling(self, interval: float) -> None:
        """Start periodic background refresh.

        Args:
            interval: Seconds between refresh attempts.
        """
        self.stop_polling()
        self._poll_interval = interval
        self._schedule_next_poll()

    def stop_polling(self) -> None:
        """Stop background polling if active."""
        self._poll_interval = None
        if self._poll_timer is not None:
            self._poll_timer.cancel()
            self._poll_timer = None

    def _schedule_next_poll(self) -> None:
        if self._poll_interval is None:
            return
        self._poll_timer = threading.Timer(self._poll_interval, self._poll_tick)
        self._poll_timer.daemon = True
        self._poll_timer.start()

    def _poll_tick(self) -> None:
        with self._refresh_lock:
            try:
                self.refresh()
            except Exception:
                logger.exception("MCP refresh poll failed")
        self._schedule_next_poll()

    # ---- Lifecycle ----

    async def close(self) -> None:
        """Close all persistent connections (async)."""
        self.stop_polling()
        for connection in self._connections:
            await connection.close()
        self._connections.clear()

    def close_sync(self) -> None:
        """Close all persistent connections (sync).

        Shuts down background loop threads without requiring an
        event loop in the calling thread.
        """
        self.stop_polling()
        for connection in self._connections:
            connection.close_sync()
        self._connections.clear()
