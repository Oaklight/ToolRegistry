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
from typing import Any

import pytest

import toolregistry._netpolicy as netpolicy
import toolregistry.integrations.mcp.client as mcp_client
from toolregistry._netpolicy import UnsafeAddressError, clear_address_cache
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
        # The interpreter running ToolRegistry, not whichever ``python``
        # happens to be first on PATH (#323).
        assert params.command == sys.executable
        assert params.args == ["/some/server.py"]

    def test_python_script_ignores_path_interpreter(self, monkeypatch, tmp_path):
        """A shadowing ``python`` on PATH must not be used for .py sources."""
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        shadow = fake_bin / "python"
        shadow.write_text("#!/bin/sh\nexit 1\n")
        shadow.chmod(0o755)
        monkeypatch.setenv("PATH", f"{fake_bin}")

        params = _to_stdio_params("/some/server.py")
        assert params.command == sys.executable

    def test_python_script_falls_back_without_executable(self, monkeypatch):
        """Embedded interpreters report an empty sys.executable."""
        monkeypatch.setattr(sys, "executable", "")
        params = _to_stdio_params("/some/server.py")
        assert params.command == "python"

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
            assert len(tools) == 4

    @pytest.mark.skipif(
        sys.platform == "win32", reason="uses a POSIX shell shim for python"
    )
    @pytest.mark.asyncio
    async def test_script_path_source_with_poisoned_path(self, tmp_path, monkeypatch):
        """The server still starts when the PATH python cannot run (#323).

        ``python`` on PATH is replaced by a script that exits immediately.
        The server only starts if the client launches it with
        ``sys.executable``; with a PATH lookup it dies at import and the
        client would see ``Connection closed``.
        """
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        shadow = fake_bin / "python"
        shadow.write_text("#!/bin/sh\nexit 1\n")
        shadow.chmod(0o755)
        monkeypatch.setenv("PATH", str(fake_bin))

        async with MCPClient(_SERVER_SCRIPT) as client:
            tools = await client.list_tools()
            assert len(tools) == 4


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
        async with MCPClient(
            f"http://127.0.0.1:{port}/mcp", allow_private_hosts=True
        ) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "add" in names
            assert "echo" in names
            assert "greet" in names

    @pytest.mark.asyncio
    async def test_call_tool_add(self, http_server):
        port, _ = http_server
        await _wait_for_port(port)
        async with MCPClient(
            f"http://127.0.0.1:{port}/mcp", allow_private_hosts=True
        ) as client:
            result = await client.call_tool("add", {"a": 10, "b": 20})
            text = result.content[0].text
            assert json.loads(text) == {"result": 30}

    @pytest.mark.asyncio
    async def test_call_tool_echo(self, http_server):
        port, _ = http_server
        await _wait_for_port(port)
        async with MCPClient(
            f"http://127.0.0.1:{port}/mcp", allow_private_hosts=True
        ) as client:
            result = await client.call_tool("echo", {"message": "http-test"})
            assert result.content[0].text == "http-test"

    @pytest.mark.asyncio
    async def test_headers_passed(self, http_server):
        """Verify that custom headers do not break the connection."""
        port, _ = http_server
        await _wait_for_port(port)
        headers = {"X-Custom-Header": "test-value"}
        async with MCPClient(
            f"http://127.0.0.1:{port}/mcp",
            headers=headers,
            allow_private_hosts=True,
        ) as client:
            tools = await client.list_tools()
            assert len(tools) == 4


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
        async with MCPClient(
            f"http://127.0.0.1:{port}/sse", allow_private_hosts=True
        ) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert "add" in names
            assert "echo" in names
            assert "greet" in names

    @pytest.mark.asyncio
    async def test_call_tool_add(self, sse_server):
        port, _ = sse_server
        await _wait_for_port(port)
        async with MCPClient(
            f"http://127.0.0.1:{port}/sse", allow_private_hosts=True
        ) as client:
            result = await client.call_tool("add", {"a": 100, "b": 200})
            text = result.content[0].text
            assert json.loads(text) == {"result": 300}

    @pytest.mark.asyncio
    async def test_call_tool_greet(self, sse_server):
        port, _ = sse_server
        await _wait_for_port(port)
        async with MCPClient(
            f"http://127.0.0.1:{port}/sse", allow_private_hosts=True
        ) as client:
            result = await client.call_tool("greet", {"name": "SSE"})
            assert result.content[0].text == "Hello, SSE!"

    @pytest.mark.asyncio
    async def test_headers_passed(self, sse_server):
        """Verify that custom headers do not break the SSE connection."""
        port, _ = sse_server
        await _wait_for_port(port)
        headers = {"Authorization": "Bearer test-token"}
        async with MCPClient(
            f"http://127.0.0.1:{port}/sse",
            headers=headers,
            allow_private_hosts=True,
        ) as client:
            tools = await client.list_tools()
            assert len(tools) == 4


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


class _FakeStreams:
    """Async context manager that records the transport it stands for."""

    def __init__(self, calls: list[str], label: str) -> None:
        self._calls = calls
        self._label = label

    async def __aenter__(self):
        self._calls.append(self._label)
        return (object(), object())

    async def __aexit__(self, *exc):
        return False


def _stub_transport(calls: list[str], label: str):
    def factory(*args, **kwargs):
        return _FakeStreams(calls, label)

    return factory


class TestOutboundAddressPolicy:
    """URL transports refuse non-public hosts before opening a connection."""

    @pytest.mark.asyncio
    async def test_streamable_http_refuses_loopback_by_default(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            mcp_client,
            "get_streamable_http_client",
            lambda: _stub_transport(calls, "streamable"),
        )

        client = MCPClient("http://127.0.0.1:9/mcp")
        with pytest.raises(UnsafeAddressError):
            async with client._open_transport():
                pass
        assert calls == []

    @pytest.mark.asyncio
    async def test_sse_refuses_loopback_by_default(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(mcp_client, "sse_client", _stub_transport(calls, "sse"))

        client = MCPClient("http://127.0.0.1:9/sse")
        with pytest.raises(UnsafeAddressError):
            async with client._open_transport():
                pass
        assert calls == []

    @pytest.mark.asyncio
    async def test_websocket_refuses_loopback_by_default(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            mcp_client,
            "get_websocket_client",
            lambda: _stub_transport(calls, "websocket"),
        )

        client = MCPClient("ws://127.0.0.1:9/ws")
        with pytest.raises(UnsafeAddressError):
            async with client._open_transport():
                pass
        assert calls == []

    @pytest.mark.asyncio
    async def test_private_host_opt_in_reaches_the_transport(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            mcp_client,
            "get_streamable_http_client",
            lambda: _stub_transport(calls, "streamable"),
        )

        client = MCPClient("http://127.0.0.1:9/mcp", allow_private_hosts=True)
        async with client._open_transport():
            pass
        assert calls == ["streamable"]

    @pytest.mark.asyncio
    async def test_public_host_reaches_the_transport(self, monkeypatch):
        calls: list[str] = []
        monkeypatch.setattr(
            mcp_client,
            "get_streamable_http_client",
            lambda: _stub_transport(calls, "streamable"),
        )

        async def resolve(host, port, timeout=5.0):
            return ["93.184.216.34"]

        monkeypatch.setattr(netpolicy, "_resolve_async", resolve)
        clear_address_cache()
        try:
            client = MCPClient("https://mcp.example/mcp")
            async with client._open_transport():
                pass
        finally:
            clear_address_cache()
        assert calls == ["streamable"]

    @pytest.mark.asyncio
    async def test_refusal_names_the_switch_without_the_resolved_address(
        self, monkeypatch
    ):
        async def resolve(host, port, timeout=5.0):
            return ["127.0.0.1"]

        monkeypatch.setattr(netpolicy, "_resolve_async", resolve)
        clear_address_cache()
        try:
            client = MCPClient("http://localhost:9/mcp")
            with pytest.raises(UnsafeAddressError) as excinfo:
                async with client._open_transport():
                    pass
        finally:
            clear_address_cache()

        message = str(excinfo.value)
        assert "allow_private_hosts" in message
        assert "127.0.0.1" not in message
        assert "localhost" in message

    @pytest.mark.asyncio
    async def test_resolution_failure_is_refused_without_detail(self, monkeypatch):
        async def resolve(host, port, timeout=5.0):
            raise OSError("resolver detail")

        monkeypatch.setattr(netpolicy, "_resolve_async", resolve)
        clear_address_cache()

        client = MCPClient("http://unresolvable.example/mcp")
        with pytest.raises(UnsafeAddressError) as excinfo:
            async with client._open_transport():
                pass

        message = str(excinfo.value)
        assert "allow_private_hosts" not in message
        assert "resolver detail" not in message
        assert "could not be resolved" in message

    @pytest.mark.asyncio
    async def test_sse_uses_a_no_redirect_client(self, monkeypatch):
        captured: dict[str, Any] = {}
        made: dict[str, Any] = {}

        def make_client(**kwargs):
            made.update(kwargs)
            return object()

        def fake_sse(url, **kwargs):
            captured["factory"] = kwargs["httpx_client_factory"]
            return _FakeStreams([], "sse")

        monkeypatch.setattr(mcp_client, "make_async_http_client", make_client)
        monkeypatch.setattr(mcp_client, "sse_client", fake_sse)

        client = MCPClient("http://127.0.0.1:9/sse", allow_private_hosts=True)
        async with client._open_transport():
            pass

        factory = captured["factory"]
        assert callable(factory)
        factory(headers=None)
        assert made["follow_redirects"] is False

    @pytest.mark.asyncio
    async def test_streamable_old_style_uses_a_no_redirect_client(self, monkeypatch):
        captured: dict[str, Any] = {}
        made: dict[str, Any] = {}

        def make_client(**kwargs):
            made.update(kwargs)
            return object()

        def fake_streamable(url, *, headers=None, httpx_client_factory=None):
            captured["factory"] = httpx_client_factory
            return _FakeStreams([], "streamable")

        monkeypatch.setattr(mcp_client, "make_async_http_client", make_client)
        monkeypatch.setattr(
            mcp_client, "get_streamable_http_client", lambda: fake_streamable
        )

        client = MCPClient("http://127.0.0.1:9/mcp", allow_private_hosts=True)
        async with client._open_transport():
            pass

        factory = captured["factory"]
        factory(headers=None)
        assert made["follow_redirects"] is False

    @pytest.mark.asyncio
    async def test_streamable_new_style_uses_a_no_redirect_client(self, monkeypatch):
        captured: dict[str, Any] = {}

        def fake_streamable(url, *, http_client=None, terminate_on_close=True):
            captured["client"] = http_client
            return _FakeStreams([], "streamable")

        monkeypatch.setattr(
            mcp_client, "get_streamable_http_client", lambda: fake_streamable
        )

        client = MCPClient("http://127.0.0.1:9/mcp", allow_private_hosts=True)
        async with client._open_transport():
            pass

        assert captured["client"].follow_redirects is False
