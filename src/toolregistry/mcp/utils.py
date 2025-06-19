from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastmcp.client import ClientTransport  # type: ignore
from fastmcp.client.transports import (  # type: ignore
    FastMCPTransport,
    SSETransport,
    StdioTransport,
    StreamableHttpTransport,
    WSTransport,
    infer_transport,
)
from fastmcp.server import FastMCP as FastMCPServer  # type: ignore
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.websocket import websocket_client
from mcp.server.fastmcp import FastMCP as FastMCP1Server  # type: ignore
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import InitializeResult
from pydantic import AnyUrl


def infer_transport_overriden(
    transport: ClientTransport
    | FastMCPServer
    | FastMCP1Server
    | AnyUrl
    | Path
    | dict[str, Any]
    | str,
) -> ClientTransport:
    """
    Infer the appropriate transport type from the given transport argument.
    This override only applies to FastMCP versions <= 2.3.5.

    For FastMCP > 2.3.5, falls back to the default `infer_transport` function.
    """
    from importlib.metadata import version

    from packaging import version as pkg_version

    # Skip override if FastMCP version > 2.3.5
    if pkg_version.parse(version("fastmcp")) > pkg_version.parse("2.3.5"):
        return infer_transport(transport)

    if isinstance(transport, AnyUrl | str) and str(transport).startswith("http"):
        parsed_url = urlparse(str(transport))
        path = parsed_url.path

        if "/sse/" in path or path.rstrip("/").endswith("/sse"):
            return SSETransport(url=transport)
        else:
            return StreamableHttpTransport(url=transport)

    return infer_transport(transport)


async def get_initialize_result(transport: ClientTransport) -> InitializeResult:
    """
    Handles initialization for different types of ClientTransport.

    This function analyzes the given transport type and applies the appropriate
    initialization process, yielding an `InitializeResult` object.

    Args:
        transport: The ClientTransport instance to initialize.

    Returns:
        InitializeResult: The result of the session initialization.

    Raises:
        ValueError: Raised if the transport type is unsupported or initialization fails.
    """

    async def handle_transport(transport_creator, *args, **kwargs) -> InitializeResult:
        """
        Generic transport handling logic.

        Creates and manages a transport instance, extracts streams, and uses
        them to initialize a `ClientSession`.

        Args:
            transport_creator: The client creation method (e.g., websocket_client).
            *args: Positional arguments passed to the transport creator.
            **kwargs: Keyword arguments passed to the transport creator.

        Returns:
            InitializeResult: The initialization result from the session.
        """
        async with transport_creator(*args, **kwargs) as transport:
            # Unified unpacking logic to handle streams returned by different transports (2 or 3 items).
            read_stream, write_stream, *_ = (
                transport  # Use *_ to ignore extra parameters.
            )
            async with ClientSession(read_stream, write_stream) as session:
                return await session.initialize()  # Return the initialization result.

    try:
        # Handle WebSocket transport
        if isinstance(transport, WSTransport):
            return await handle_transport(websocket_client, transport.url)

        # Handle Server-Sent Events (SSE) transport
        elif isinstance(transport, SSETransport):
            return await handle_transport(
                sse_client, transport.url, headers=transport.headers
            )

        # Handle Streamable HTTP transport
        elif isinstance(transport, StreamableHttpTransport):
            return await handle_transport(
                streamablehttp_client, transport.url, headers=transport.headers
            )

        # Handle Stdio transport (subprocess-based transport)
        elif isinstance(transport, StdioTransport):
            server_params = StdioServerParameters(
                command=transport.command,
                args=transport.args,
                env=transport.env,
                cwd=transport.cwd,
            )
            return await handle_transport(stdio_client, server_params)

        # Handle FastMCP in-memory transport
        elif isinstance(transport, FastMCPTransport):
            async with create_connected_server_and_client_session(
                server=transport._fastmcp._mcp_server
            ) as session:
                return await session.initialize()

        # Raise an error if the transport type is unsupported
        else:
            raise ValueError(f"Unsupported transport type: {type(transport)}")

    except Exception as e:
        raise ValueError(f"Failed to initialize transport: {str(e)}") from e
