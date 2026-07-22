from pathlib import Path
from typing import Any
from collections.abc import Callable

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
            is_error = getattr(result, "is_error", None) or getattr(
                result, "isError", False
            )
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
                    "media_type": content.mimeType,
                    "data": content.data,
                },
            }

        def process_embedded(content: EmbeddedResource) -> dict:
            if isinstance(content.resource, TextResourceContents):
                return {"type": "text", "text": content.resource.text}
            elif isinstance(content.resource, BlobResourceContents):
                mime = content.resource.mimeType or ""
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
        input_schema = getattr(tool_spec, "input_schema", None) or getattr(
            tool_spec, "inputSchema", {}
        )
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

    async def register_mcp_tools_async(
        self,
        transport: str | dict[str, Any] | Path,
        namespace: bool | str = False,
        persistent: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Async implementation to register all tools from an MCP server.

        Args:
            transport (Union[str, Dict[str, Any], Path]): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Dict with "command", "args", "env" keys for stdio transport
            namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If ``False``, no namespace is used.
                - If ``True``, the namespace is derived from the server info name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            persistent (bool): If True (default), keep the connection open
                across tool calls. If False, create a new connection per call.
            headers (Optional[Dict[str, str]]): HTTP headers for SSE or
                streamable-http transports (e.g. authentication).

        Raises:
            RuntimeError: If connection to server fails.
        """
        connection = MCPConnectionManager(
            transport=transport,
            persistent=persistent,
            headers=headers,
        )
        self._connections.append(connection)

        # Use a temporary connection for tool discovery
        async with MCPClient(transport, headers=headers) as client:
            server_info: Implementation | None = client.server_info

            if isinstance(namespace, str):
                resolved_ns = namespace
            elif namespace:  # namespace is True
                resolved_ns = server_info.name if server_info else "MCP sse service"
            else:
                resolved_ns = None

            # Get available tools from server
            tools_response: list[ToolSpec] = await client.list_tools()

            # Register each tool with the shared connection manager
            for tool_spec in tools_response:
                mcp_tool = MCPTool.from_tool_json(
                    tool_spec=tool_spec,
                    connection=connection,
                    namespace=resolved_ns,
                )

                self.registry.register(mcp_tool, namespace=resolved_ns)

    def register_mcp_tools(
        self,
        transport: str | dict[str, Any] | Path,
        namespace: bool | str = False,
        persistent: bool = True,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Register all tools from an MCP server (synchronous entry point).

        Uses the shared :class:`AsyncRuntime` event loop so that
        multiple sequential registrations (e.g. stdio + HTTP) do not
        interfere with each other's anyio resources.

        Args:
            transport (Union[str, Dict[str, Any], Path]): Can be:
                - URL string (http(s)://, ws(s)://)
                - Path to script file (.py, .js)
                - Dict with "command", "args", "env" keys for stdio transport
            namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If ``False``, no namespace is used.
                - If ``True``, the namespace is derived from the server info name.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            persistent (bool): If True (default), keep the connection open
                across tool calls. If False, create a new connection per call.
            headers (Optional[Dict[str, str]]): HTTP headers for SSE or
                streamable-http transports (e.g. authentication).
        """
        from ..._async_runtime import AsyncRuntime

        AsyncRuntime.run_sync(
            self.register_mcp_tools_async(
                transport, namespace, persistent, headers=headers
            )
        )

    async def close(self) -> None:
        """Close all persistent connections (async)."""
        for connection in self._connections:
            await connection.close()
        self._connections.clear()

    def close_sync(self) -> None:
        """Close all persistent connections (sync).

        Shuts down background loop threads without requiring an
        event loop in the calling thread.
        """
        for connection in self._connections:
            connection.close_sync()
        self._connections.clear()
