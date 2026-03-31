"""Minimal MCP client adapter over the official ``mcp`` SDK.

Supports stdio, SSE, streamable-http, and websocket transports.
This is the sole point of contact with the ``mcp`` package for
client-side operations.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.client.websocket import websocket_client
from mcp.types import CallToolResult
from mcp.types import Tool as ToolSpec


class MCPClient:
    """Thin async context manager around mcp.ClientSession.

    Usage:
        async with MCPClient("http://localhost:8000/mcp") as client:
            tools = await client.list_tools()
            result = await client.call_tool("tool_name", {"arg": "value"})
    """

    def __init__(
        self,
        source: str | dict | Path,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize MCPClient.

        Args:
            source: Connection target. Can be:
                - HTTP(S) URL string for SSE or streamable-http transport
                - WS(S) URL string for websocket transport
                - Dict with "command", "args", "env" keys for stdio transport
                - Path or string path to a .py/.js script for stdio transport
            headers: Optional HTTP headers to send with SSE or streamable-http
                requests (e.g. for authentication). Ignored for stdio and
                websocket transports.
        """
        self._source = source
        self._headers = headers
        self._session: ClientSession | None = None
        self._cm = None  # transport context manager
        self._session_cm = None  # session context manager

    @asynccontextmanager
    async def _open_transport(self):
        """Open the appropriate transport based on the source type.

        Yields:
            Tuple of (read_stream, write_stream) for ClientSession.
        """
        src = self._source
        if isinstance(src, str) and src.startswith(("http://", "https://")):
            parsed = urlparse(src)
            if parsed.path.rstrip("/").endswith("/sse"):
                async with sse_client(src, headers=self._headers) as (r, w):
                    yield r, w
            else:
                http_client = (
                    httpx.AsyncClient(headers=self._headers) if self._headers else None
                )
                async with streamable_http_client(src, http_client=http_client) as (
                    r,
                    w,
                    _,
                ):
                    yield r, w
        elif isinstance(src, str) and src.startswith(("ws://", "wss://")):
            async with websocket_client(src) as (r, w):
                yield r, w
        else:
            params = _to_stdio_params(src)
            async with stdio_client(params) as (r, w):
                yield r, w

    async def __aenter__(self) -> "MCPClient":
        self._cm = self._open_transport()
        r, w = await self._cm.__aenter__()
        self._session = ClientSession(r, w)
        self._session_cm = self._session.__aenter__()
        await self._session_cm
        await self._session.initialize()
        return self

    async def __aexit__(self, *exc):
        try:
            if self._session is not None:
                await self._session.__aexit__(*exc)
        finally:
            if self._cm is not None:
                await self._cm.__aexit__(*exc)

    async def list_tools(self) -> list[ToolSpec]:
        """List available tools from the MCP server.

        Returns:
            List of ToolSpec objects describing available tools.
        """
        assert self._session is not None, (
            "MCPClient must be used as async context manager"
        )
        result = await self._session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Call a tool on the MCP server.

        Args:
            name: Name of the tool to call.
            arguments: Dictionary of arguments to pass to the tool.

        Returns:
            CallToolResult from the MCP server.
        """
        assert self._session is not None, (
            "MCPClient must be used as async context manager"
        )
        return await self._session.call_tool(name, arguments)

    @property
    def is_connected(self) -> bool:
        """Whether the client has an active session.

        Returns:
            True if connected with an active session, False otherwise.
        """
        return self._session is not None

    @property
    def session(self) -> ClientSession | None:
        """Access the underlying ClientSession.

        Returns:
            The active ClientSession, or None if not connected.
        """
        return self._session

    @property
    def server_info(self):
        """Access server information from the initialization result.

        Returns:
            Server info from the session, or None if not available.
        """
        if self._session is None:
            return None
        # Try v1 camelCase first, then v2 snake_case
        init_result = getattr(self._session, "initialize_result", None)
        if init_result is None:
            return None
        return getattr(init_result, "serverInfo", None) or getattr(
            init_result, "server_info", None
        )

    @property
    def initialize_result(self):
        """Access the full initialization result.

        Returns:
            The InitializeResult from the session, or None.
        """
        return getattr(self._session, "initialize_result", None)


def _to_stdio_params(src: str | dict | Path) -> StdioServerParameters:
    """Convert a source specification to StdioServerParameters.

    Args:
        src: Source specification. Can be:
            - Dict with "command" key (and optional "args", "env")
            - Path to a .py or .js script
            - String path to an executable

    Returns:
        StdioServerParameters configured for the given source.
    """
    if isinstance(src, dict):
        return StdioServerParameters(
            command=src["command"],
            args=src.get("args", []),
            env=src.get("env"),
        )
    path = Path(src) if not isinstance(src, Path) else src
    if path.suffix == ".py":
        return StdioServerParameters(command="python", args=[str(path)])
    if path.suffix == ".js":
        return StdioServerParameters(command="node", args=[str(path)])
    return StdioServerParameters(command=str(path), args=[])
