"""MCP SDK v1/v2 compatibility layer (client side).

Abstracts the breaking changes between mcp v1.x and v2.x so that
client.py, integration.py, and connection.py work with either version.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Version detection
# ---------------------------------------------------------------------------


def _detect_mcp_version() -> int:
    try:
        from mcp.shared.exceptions import MCPError  # noqa: F811

        del MCPError
        return 2
    except ImportError:
        return 1


MCP_VERSION: int = _detect_mcp_version()

# ---------------------------------------------------------------------------
# HTTP client factory — httpx (v1) vs httpx2 (v2)
# ---------------------------------------------------------------------------


def make_async_http_client(**kwargs: Any) -> Any:
    """Create an async HTTP client compatible with the installed mcp version.

    v1 uses ``httpx.AsyncClient``, v2 uses ``httpx2.AsyncClient``.
    """
    if MCP_VERSION >= 2:
        import httpx2  # type: ignore[import-untyped]

        return httpx2.AsyncClient(**kwargs)
    else:
        import httpx

        return httpx.AsyncClient(**kwargs)


# ---------------------------------------------------------------------------
# WebSocket transport — removed in v2
# ---------------------------------------------------------------------------


def get_websocket_client() -> Any:
    """Return the websocket_client transport function.

    Raises:
        ImportError: On mcp v2 where WebSocket transport was removed.
    """
    if MCP_VERSION >= 2:
        raise ImportError(
            "WebSocket transport was removed in mcp v2. "
            "Use streamable-http (http://) or SSE (/sse) instead."
        )
    from mcp.client.websocket import websocket_client

    return websocket_client


# ---------------------------------------------------------------------------
# Field accessor
# ---------------------------------------------------------------------------


def get_field(obj: Any, snake_name: str, camel_name: str, default: Any = None) -> Any:
    """Access a field that may be snake_case (v2) or camelCase (v1).

    Tries snake_case first (v2 attribute access), then camelCase (v1).
    """
    val = getattr(obj, snake_name, None)
    if val is not None:
        return val
    return getattr(obj, camel_name, default)


__all__ = [
    "MCP_VERSION",
    "get_field",
    "get_websocket_client",
    "make_async_http_client",
]
