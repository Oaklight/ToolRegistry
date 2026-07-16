"""Persistent connection manager for MCP servers."""

import asyncio
import threading
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

    For sync callers, a background daemon thread with its own event loop
    is lazily created on the first ``call_tool_sync()`` call.  This keeps
    the loop (and therefore the MCP transport) alive across calls.  Async
    callers use the caller's own loop and are unaffected.

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

        self._sync_loop: asyncio.AbstractEventLoop | None = None
        self._sync_thread: threading.Thread | None = None

    @property
    def transport(self) -> str | dict | Path:
        """The transport source for the MCP server."""
        return self._transport

    @property
    def is_connected(self) -> bool:
        """Whether an active session exists."""
        return self._client is not None and self._client.is_connected

    # -- Async API (unchanged) --------------------------------------

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

    # -- Sync API (background loop thread) --------------------------

    def _ensure_sync_loop(self) -> asyncio.AbstractEventLoop:
        """Start the background event-loop thread if not already running.

        Returns:
            The persistent event loop running in the daemon thread.
        """
        if self._sync_loop is not None and self._sync_loop.is_running():
            return self._sync_loop

        loop = asyncio.new_event_loop()
        self._sync_loop = loop

        def _run() -> None:
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._sync_thread = t
        return loop

    def call_tool_sync(self, name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Call a tool synchronously using a persistent background loop.

        The first call lazily starts a daemon thread whose event loop
        keeps MCP transport resources alive across calls.

        Args:
            name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            CallToolResult from the MCP server.
        """
        loop = self._ensure_sync_loop()
        future = asyncio.run_coroutine_threadsafe(self.call_tool(name, arguments), loop)
        return future.result()

    # -- Lifecycle --------------------------------------------------

    async def close(self) -> None:
        """Close the persistent connection and stop the sync loop thread."""
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception:
                    pass
                self._client = None
        self._stop_sync_loop()

    def close_sync(self) -> None:
        """Close from sync context — tear down background thread and connection."""
        loop = self._sync_loop
        if loop is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._close_client(), loop)
            try:
                future.result(timeout=10)
            except Exception:
                pass
        self._stop_sync_loop()

    async def _close_client(self) -> None:
        """Close the MCP client under lock (runs on the sync loop thread)."""
        async with self._lock:
            if self._client is not None:
                try:
                    await self._client.__aexit__(None, None, None)
                except Exception:
                    pass
                self._client = None

    def _stop_sync_loop(self) -> None:
        """Stop the background event loop and join its thread."""
        loop = self._sync_loop
        thread = self._sync_thread
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)
        if loop is not None and not loop.is_closed():
            loop.close()
        self._sync_loop = None
        self._sync_thread = None

    def __del__(self) -> None:
        """Best-effort cleanup of the background thread."""
        try:
            self._stop_sync_loop()
        except Exception:
            pass

    # -- Pickling support (for ProcessPoolBackend) ------------------

    def __getstate__(self) -> dict:
        """Drop live connection state before pickling.

        The config (transport, headers, persistent flag) is preserved.
        The live ``_client`` (holding OS sockets), ``_lock``
        (event-loop-bound), and sync loop thread are dropped.  The
        worker process will reconnect lazily on first ``call_tool()``.
        """
        return {
            "_transport": self._transport,
            "_headers": self._headers,
            "_persistent": self._persistent,
        }

    def __setstate__(self, state: dict) -> None:
        """Restore config; connection will be re-established lazily."""
        self._transport = state["_transport"]
        self._headers = state["_headers"]
        self._persistent = state["_persistent"]
        self._client = None
        self._lock = asyncio.Lock()
        self._sync_loop = None
        self._sync_thread = None
