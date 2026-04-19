"""Persistent connection manager for MCP servers."""

import asyncio
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult

from ..._vendor.structlog import get_logger
from .client import MCPClient

logger = get_logger()


class MCPConnectionManager:
    """Persistent connection manager for an MCP server.

    All tools registered from the same server share this connection.
    Supports lazy connect on first call and auto-reconnect on failure.

    Args:
        transport: MCP server source (URL, dict, or Path).
        headers: Optional HTTP headers for SSE/streamable-http transports.
        persistent: If True (default), keep the connection open across calls.
            If False, create a new connection per call (original behavior).
    """

    def __init__(
        self,
        transport: str | dict | Path,
        headers: dict[str, str] | None = None,
        persistent: bool = True,
    ) -> None:
        self._transport = transport
        self._headers = headers
        self._persistent = persistent
        self._client: MCPClient | None = None
        self._lock = asyncio.Lock()

    @property
    def transport(self) -> str | dict | Path:
        """The transport source for the MCP server."""
        return self._transport

    @property
    def is_connected(self) -> bool:
        """Whether an active session exists."""
        return self._client is not None and self._client.is_connected

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Call a tool on the MCP server.

        Uses persistent or per-request connection based on config.

        Args:
            name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            CallToolResult from the MCP server.
        """
        if not self._persistent:
            return await self._call_per_request(name, arguments)
        return await self._call_persistent(name, arguments)

    async def list_tools(self):
        """List available tools using a temporary connection.

        Returns:
            List of ToolSpec objects.
        """
        async with MCPClient(self._transport, self._headers) as client:
            return await client.list_tools()

    async def _ensure_connected(self) -> None:
        """Connect if not already connected. Must be called under lock."""
        if self._client is None or not self._client.is_connected:
            await self._connect()

    async def _connect(self) -> None:
        """Establish (or re-establish) connection."""
        if self._client is not None:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass
        self._client = MCPClient(self._transport, self._headers)
        await self._client.__aenter__()

    async def _call_persistent(
        self, name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        """Call tool using a persistent connection with auto-reconnect."""
        async with self._lock:
            await self._ensure_connected()
        try:
            assert self._client is not None
            return await self._client.call_tool(name, arguments)
        except Exception:
            logger.warning(f"MCP call to '{name}' failed, reconnecting and retrying")
            async with self._lock:
                await self._connect()
            assert self._client is not None
            return await self._client.call_tool(name, arguments)

    async def _call_per_request(
        self, name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        """Call tool using a fresh connection (original behavior)."""
        async with MCPClient(self._transport, self._headers) as client:
            return await client.call_tool(name, arguments)

    async def close(self) -> None:
        """Close the persistent connection."""
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception:
                    pass
                self._client = None
