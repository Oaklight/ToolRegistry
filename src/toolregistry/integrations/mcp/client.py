"""Minimal MCP client adapter over the official ``mcp`` SDK.

Supports stdio, SSE, streamable-http, and websocket transports.
This is the sole point of contact with the ``mcp`` package for
client-side operations.
"""

from contextlib import asynccontextmanager
import inspect
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult
from mcp.types import Tool as ToolSpec

from ..._netpolicy import (
    PrivateAddressError,
    UnsafeAddressError,
    validate_outbound_url_async,
)
from ._compat import (
    MCP_VERSION,
    get_streamable_http_client,
    get_websocket_client,
    make_async_http_client,
)

#: URL schemes that reach the network and therefore pass the address policy.
_URL_SCHEMES = ("http://", "https://", "ws://", "wss://")


def _resolution_error(url: str) -> UnsafeAddressError:
    """Build a refusal for an unresolvable name without exposing DNS detail."""
    try:
        host = urlparse(url).hostname or "(unknown host)"
    except ValueError:
        host = "(unknown host)"
    return UnsafeAddressError(
        f"Refusing to contact '{host}': the host name could not be resolved."
    )


def _http_timeout() -> Any:
    """Return the MCP transports' recommended HTTP timeout."""
    if MCP_VERSION >= 2:
        import httpx2  # type: ignore[import-untyped]

        return httpx2.Timeout(30.0, read=300.0)
    import httpx

    return httpx.Timeout(30.0, read=300.0)


def _http_client(**kwargs: Any) -> Any:
    """Create the MCP HTTP client with redirects disabled.

    mcp v1's default client enables redirects, so a public endpoint could
    redirect a request to a private host. mcp v2 enforces its own same-origin
    redirect rule and does not consult ``follow_redirects``; the flag is
    harmless there and keeps both versions explicit.
    """
    kwargs.setdefault("follow_redirects", False)
    kwargs.setdefault("timeout", _http_timeout())
    return make_async_http_client(**kwargs)


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
        allow_private_hosts: bool = False,
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
            allow_private_hosts: Allow a URL transport to reach loopback,
                link-local or private addresses. The default refuses them
                before any connection is opened.
        """
        self._source = source
        self._headers = headers
        self._allow_private_hosts = allow_private_hosts
        self._session: ClientSession | None = None
        self._cm = None  # transport context manager
        self._session_cm = None  # session context manager

    @asynccontextmanager
    async def _open_transport(self):
        """Open the appropriate transport based on the source type.

        Every URL transport passes the outbound address policy before a
        connection is opened; the policy's ``SCHEMES`` covers ``http(s)`` and
        ``ws(s)``.

        Yields:
            Tuple of (read_stream, write_stream) for ClientSession.
        """
        src = self._source
        if isinstance(src, str) and src.startswith(_URL_SCHEMES):
            try:
                await validate_outbound_url_async(
                    src,
                    allow_private_hosts=self._allow_private_hosts,
                )
            except PrivateAddressError:
                # The policy already names the switch and omits the resolved
                # address; keep its type and ``addresses`` attribute.
                raise
            except UnsafeAddressError:
                # A resolution failure carries resolver text; replace it with
                # a message that exposes no lookup detail and does not suggest
                # the private-host switch, which cannot help a failed lookup.
                raise _resolution_error(src) from None

        if isinstance(src, str) and src.startswith(("http://", "https://")):
            parsed = urlparse(src)
            if parsed.path.rstrip("/").endswith("/sse"):
                async with sse_client(
                    src,
                    headers=self._headers,
                    httpx_client_factory=_http_client,
                ) as (r, w):
                    yield r, w
            else:
                _streamable_http = get_streamable_http_client()
                # mcp >= 1.24's ``streamable_http_client`` (also the v2 name)
                # takes a ready client; the older v1 transport takes headers
                # and a factory. Inspect the signature instead of the version:
                # mcp 1.24-1.29 reports version 1 for both names.
                if "http_client" in inspect.signature(_streamable_http).parameters:
                    http_client = _http_client(headers=self._headers)
                    try:
                        async with _streamable_http(
                            src, http_client=http_client
                        ) as streams:
                            r, w = streams[0], streams[1]
                            yield r, w
                    finally:
                        await http_client.aclose()
                else:
                    async with _streamable_http(
                        src,
                        headers=self._headers,
                        httpx_client_factory=_http_client,
                    ) as streams:
                        r, w = streams[0], streams[1]
                        yield r, w
        elif isinstance(src, str) and src.startswith(("ws://", "wss://")):
            ws_client = get_websocket_client()
            async with ws_client(src) as (r, w):
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
        init_result = getattr(self._session, "initialize_result", None)
        if init_result is None:
            return None
        from ._compat import get_field

        return get_field(init_result, "server_info", "serverInfo")

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

    A ``.py`` script runs under :data:`sys.executable`, the interpreter that
    imported ToolRegistry.  Using the ``python`` found on ``PATH`` can start
    the server in a different environment that does not have the server's
    dependencies, which surfaces only as ``Connection closed``.  Callers
    that need a specific interpreter can pass the dict form explicitly.
    """
    if isinstance(src, dict):
        return StdioServerParameters(
            command=src["command"],
            args=src.get("args", []),
            env=src.get("env"),
        )
    path = Path(src) if not isinstance(src, Path) else src
    if path.suffix == ".py":
        # sys.executable is empty in embedded interpreters and some frozen
        # launchers; fall back to the historical PATH lookup there.
        return StdioServerParameters(
            command=sys.executable or "python", args=[str(path)]
        )
    if path.suffix == ".js":
        return StdioServerParameters(command="node", args=[str(path)])
    return StdioServerParameters(command=str(path), args=[])
