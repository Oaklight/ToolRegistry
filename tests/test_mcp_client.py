"""Integration tests for MCPClient across all supported transports.

Tests verify that MCPClient can connect to MCP servers via stdio,
streamable-http, and SSE transports, list tools, and call tools.

Requires the ``mcp`` extra: ``pip install toolregistry[mcp]``
"""

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from toolregistry.integrations.mcp.client import MCPClient, _to_stdio_params

# Path to the lightweight test MCP server script
_SERVER_SCRIPT = str(Path(__file__).parent / "_mcp_test_server.py")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_free_port() -> int:
    """Find and return a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_for_port(port: int, timeout: float = 30.0) -> None:
    """Block until *port* on localhost accepts connections."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("127.0.0.1", port))
            s.close()
            # Give the server a moment to fully initialise after binding
            await asyncio.sleep(0.5)
            return
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.5)
    raise TimeoutError(f"Port {port} did not open within {timeout}s")


# ---------------------------------------------------------------------------
# Unit tests for _to_stdio_params
# ---------------------------------------------------------------------------


class TestToStdioParams:
    """Tests for the _to_stdio_params helper function."""

    def test_dict_source(self):
        params = _to_stdio_params(
            {"command": "python", "args": ["-m", "server"], "env": {"K": "V"}}
        )
        assert params.command == "python"
        assert params.args == ["-m", "server"]
        assert params.env == {"K": "V"}

    def test_dict_source_defaults(self):
        params = _to_stdio_params({"command": "mybin"})
        assert params.command == "mybin"
        assert params.args == []
        assert params.env is None

    def test_python_script_path(self):
        params = _to_stdio_params("/some/server.py")
        assert params.command == "python"
        assert params.args == ["/some/server.py"]

    def test_js_script_path(self):
        params = _to_stdio_params(Path("/some/server.js"))
        assert params.command == "node"
        assert params.args == ["/some/server.js"]

    def test_generic_executable(self):
        params = _to_stdio_params("/usr/local/bin/mcp-server")
        assert params.command == "/usr/local/bin/mcp-server"
        assert params.args == []


# ---------------------------------------------------------------------------
# Integration tests – STDIO transport
# ---------------------------------------------------------------------------


class TestStdioTransport:
    """MCPClient integration tests over stdio transport."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with MCPClient(config) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "add" in names
            assert "echo" in names
            assert "greet" in names

    @pytest.mark.asyncio
    async def test_call_tool_add(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with MCPClient(config) as client:
            result = await client.call_tool("add", {"a": 5, "b": 3})
            text = result.content[0].text
            assert json.loads(text) == {"result": 8}

    @pytest.mark.asyncio
    async def test_call_tool_echo(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with MCPClient(config) as client:
            result = await client.call_tool("echo", {"message": "ping"})
            assert result.content[0].text == "ping"

    @pytest.mark.asyncio
    async def test_call_tool_greet_default(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with MCPClient(config) as client:
            result = await client.call_tool("greet", {})
            assert result.content[0].text == "Hello, World!"

    @pytest.mark.asyncio
    async def test_call_tool_greet_custom(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with MCPClient(config) as client:
            result = await client.call_tool("greet", {"name": "Alice"})
            assert result.content[0].text == "Hello, Alice!"

    @pytest.mark.asyncio
    async def test_session_property(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with MCPClient(config) as client:
            assert client.session is not None

    @pytest.mark.asyncio
    async def test_script_path_source(self):
        """MCPClient should accept a .py path directly for stdio."""
        async with MCPClient(_SERVER_SCRIPT) as client:
            tools = await client.list_tools()
            assert len(tools) == 3


# ---------------------------------------------------------------------------
# Integration tests – Streamable HTTP transport
# ---------------------------------------------------------------------------


class TestStreamableHttpTransport:
    """MCPClient integration tests over streamable-http transport."""

    @pytest.fixture()
    def http_server(self):
        """Start a test MCP server with streamable-http transport."""
        port = _get_free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                _SERVER_SCRIPT,
                "--transport",
                "streamable-http",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        yield port, proc
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    @pytest.mark.asyncio
    async def test_list_tools(self, http_server):
        port, _ = http_server
        await _wait_for_port(port)
        async with MCPClient(f"http://127.0.0.1:{port}/mcp") as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "add" in names
            assert "echo" in names
            assert "greet" in names

    @pytest.mark.asyncio
    async def test_call_tool_add(self, http_server):
        port, _ = http_server
        await _wait_for_port(port)
        async with MCPClient(f"http://127.0.0.1:{port}/mcp") as client:
            result = await client.call_tool("add", {"a": 10, "b": 20})
            text = result.content[0].text
            assert json.loads(text) == {"result": 30}

    @pytest.mark.asyncio
    async def test_call_tool_echo(self, http_server):
        port, _ = http_server
        await _wait_for_port(port)
        async with MCPClient(f"http://127.0.0.1:{port}/mcp") as client:
            result = await client.call_tool("echo", {"message": "http-test"})
            assert result.content[0].text == "http-test"

    @pytest.mark.asyncio
    async def test_headers_passed(self, http_server):
        """Verify that custom headers do not break the connection."""
        port, _ = http_server
        await _wait_for_port(port)
        headers = {"X-Custom-Header": "test-value"}
        async with MCPClient(f"http://127.0.0.1:{port}/mcp", headers=headers) as client:
            tools = await client.list_tools()
            assert len(tools) == 3


# ---------------------------------------------------------------------------
# Integration tests – SSE transport
# ---------------------------------------------------------------------------


class TestSseTransport:
    """MCPClient integration tests over SSE transport."""

    @pytest.fixture()
    def sse_server(self):
        """Start a test MCP server with SSE transport."""
        port = _get_free_port()
        proc = subprocess.Popen(
            [
                sys.executable,
                _SERVER_SCRIPT,
                "--transport",
                "sse",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        yield port, proc
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    @pytest.mark.asyncio
    async def test_list_tools(self, sse_server):
        port, _ = sse_server
        await _wait_for_port(port)
        async with MCPClient(f"http://127.0.0.1:{port}/sse") as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "add" in names
            assert "echo" in names
            assert "greet" in names

    @pytest.mark.asyncio
    async def test_call_tool_add(self, sse_server):
        port, _ = sse_server
        await _wait_for_port(port)
        async with MCPClient(f"http://127.0.0.1:{port}/sse") as client:
            result = await client.call_tool("add", {"a": 100, "b": 200})
            text = result.content[0].text
            assert json.loads(text) == {"result": 300}

    @pytest.mark.asyncio
    async def test_call_tool_greet(self, sse_server):
        port, _ = sse_server
        await _wait_for_port(port)
        async with MCPClient(f"http://127.0.0.1:{port}/sse") as client:
            result = await client.call_tool("greet", {"name": "SSE"})
            assert result.content[0].text == "Hello, SSE!"

    @pytest.mark.asyncio
    async def test_headers_passed(self, sse_server):
        """Verify that custom headers do not break the SSE connection."""
        port, _ = sse_server
        await _wait_for_port(port)
        headers = {"Authorization": "Bearer test-token"}
        async with MCPClient(f"http://127.0.0.1:{port}/sse", headers=headers) as client:
            tools = await client.list_tools()
            assert len(tools) == 3


# ---------------------------------------------------------------------------
# MCPClient API tests
# ---------------------------------------------------------------------------


class TestMCPClientAPI:
    """Tests for MCPClient properties and error handling."""

    @pytest.mark.asyncio
    async def test_session_none_before_enter(self):
        client = MCPClient("http://localhost:9999/mcp")
        assert client.session is None

    @pytest.mark.asyncio
    async def test_server_info_none_before_enter(self):
        client = MCPClient("http://localhost:9999/mcp")
        assert client.server_info is None

    @pytest.mark.asyncio
    async def test_initialize_result_none_before_enter(self):
        client = MCPClient("http://localhost:9999/mcp")
        assert client.initialize_result is None

    @pytest.mark.asyncio
    async def test_headers_default_none(self):
        client = MCPClient("http://localhost:9999/mcp")
        assert client._headers is None

    @pytest.mark.asyncio
    async def test_headers_stored(self):
        headers = {"Authorization": "Bearer token123"}
        client = MCPClient("http://localhost:9999/mcp", headers=headers)
        assert client._headers == headers
