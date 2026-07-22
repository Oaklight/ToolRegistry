"""Tests for persistent connection support in MCP and OpenAPI integrations.

Covers MCPConnectionManager, HttpClientConfig persistent clients,
ToolRegistry lifecycle (close / context manager), and backward compat.
"""

import asyncio
import json
import socket
import subprocess
import sys
from pathlib import Path
import pytest

from toolregistry import ToolRegistry
from toolregistry.integrations.mcp.connection import MCPConnectionManager
from toolregistry.utils import HttpClientConfig

_SERVER_SCRIPT = str(Path(__file__).parent / "_mcp_test_server.py")


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
            await asyncio.sleep(0.5)
            return
        except (ConnectionRefusedError, OSError):
            await asyncio.sleep(0.5)
    raise TimeoutError(f"Port {port} did not open within {timeout}s")


# ---------------------------------------------------------------------------
# MCPConnectionManager unit tests
# ---------------------------------------------------------------------------


class TestMCPConnectionManager:
    """Tests for MCPConnectionManager."""

    def test_initial_state(self):
        mgr = MCPConnectionManager("http://localhost:9999/mcp")
        assert not mgr.is_connected
        assert mgr.transport == "http://localhost:9999/mcp"

    def test_persistent_default_true(self):
        mgr = MCPConnectionManager("http://localhost:9999/mcp")
        assert mgr._persistent is True

    def test_persistent_false(self):
        mgr = MCPConnectionManager("http://localhost:9999/mcp", persistent=False)
        assert mgr._persistent is False

    @pytest.mark.asyncio
    async def test_close_when_not_connected(self):
        """close() should be safe to call when not connected."""
        mgr = MCPConnectionManager("http://localhost:9999/mcp")
        await mgr.close()
        assert not mgr.is_connected


class TestMCPConnectionManagerStdio:
    """Integration tests for MCPConnectionManager with stdio transport."""

    @pytest.mark.asyncio
    async def test_persistent_multiple_calls(self):
        """Multiple tool calls should reuse the same persistent connection."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        mgr = MCPConnectionManager(config, persistent=True)
        try:
            result1 = await mgr.call_tool("add", {"a": 1, "b": 2})
            assert mgr.is_connected
            result2 = await mgr.call_tool("add", {"a": 3, "b": 4})
            assert mgr.is_connected

            text1 = result1.content[0].text
            text2 = result2.content[0].text
            assert json.loads(text1) == {"result": 3}
            assert json.loads(text2) == {"result": 7}
        finally:
            await mgr.close()

        assert not mgr.is_connected

    @pytest.mark.asyncio
    async def test_non_persistent_creates_new_connection(self):
        """With persistent=False, each call uses a fresh connection."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        mgr = MCPConnectionManager(config, persistent=False)
        try:
            result = await mgr.call_tool("echo", {"message": "test"})
            assert result.content[0].text == "test"
            # Non-persistent manager should not hold a connection
            assert not mgr.is_connected
        finally:
            await mgr.close()

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """list_tools() uses a temporary connection for discovery."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        mgr = MCPConnectionManager(config)
        tools = await mgr.list_tools()
        names = {t.name for t in tools}
        assert "add" in names
        assert "echo" in names
        # list_tools uses temp connection, persistent state unchanged
        assert not mgr.is_connected
        await mgr.close()


class TestMCPConnectionManagerHttp:
    """Integration tests for MCPConnectionManager with HTTP transport."""

    @pytest.fixture()
    def http_server(self):
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
    async def test_persistent_connection_http(self, http_server):
        port, _ = http_server
        await _wait_for_port(port)
        mgr = MCPConnectionManager(f"http://127.0.0.1:{port}/mcp", persistent=True)
        try:
            r1 = await mgr.call_tool("add", {"a": 10, "b": 20})
            assert mgr.is_connected
            r2 = await mgr.call_tool("echo", {"message": "persistent"})
            assert mgr.is_connected

            assert json.loads(r1.content[0].text) == {"result": 30}
            assert r2.content[0].text == "persistent"
        finally:
            await mgr.close()


# ---------------------------------------------------------------------------
# HttpClientConfig persistent client tests
# ---------------------------------------------------------------------------


class TestHttpClientConfigPersistent:
    """Tests for HttpClientConfig persistent client methods."""

    def test_get_persistent_client_sync(self):
        config = HttpClientConfig(base_url="http://localhost:9999")
        client1 = config.get_persistent_client(use_async=False)
        client2 = config.get_persistent_client(use_async=False)
        assert client1 is client2
        config.close()

    @pytest.mark.asyncio
    async def test_get_persistent_client_async(self):
        config = HttpClientConfig(base_url="http://localhost:9999")
        client1 = config.get_persistent_client(use_async=True)
        client2 = config.get_persistent_client(use_async=True)
        assert client1 is client2
        await config.close_async()

    def test_close_sync(self):
        config = HttpClientConfig(base_url="http://localhost:9999")
        _ = config.get_persistent_client(use_async=False)
        assert config._sync_client is not None
        config.close()
        assert config._sync_client is None

    @pytest.mark.asyncio
    async def test_close_async(self):
        config = HttpClientConfig(base_url="http://localhost:9999")
        _ = config.get_persistent_client(use_async=True)
        _ = config.get_persistent_client(use_async=False)
        assert config._async_client is not None
        assert config._sync_client is not None
        await config.close_async()
        assert config._async_client is None
        assert config._sync_client is None

    def test_to_client_still_works(self):
        """to_client() should still create fresh clients (backward compat)."""
        config = HttpClientConfig(base_url="http://localhost:9999")
        client1 = config.to_client(use_async=False)
        client2 = config.to_client(use_async=False)
        assert client1 is not client2
        client1.close()
        client2.close()


# ---------------------------------------------------------------------------
# ToolRegistry lifecycle tests
# ---------------------------------------------------------------------------


class TestToolRegistryLifecycle:
    """Tests for ToolRegistry close() and context manager."""

    def test_sync_context_manager(self):
        with ToolRegistry() as reg:
            assert isinstance(reg, ToolRegistry)

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with ToolRegistry() as reg:
            assert isinstance(reg, ToolRegistry)

    def test_close_without_integrations(self):
        """close() should be safe even with no integrations."""
        reg = ToolRegistry()
        reg.close()

    @pytest.mark.asyncio
    async def test_close_async_without_integrations(self):
        reg = ToolRegistry()
        await reg.close_async()


class TestToolRegistryMCPIntegration:
    """Integration test: register_from_mcp with persistent connections."""

    @pytest.mark.asyncio
    async def test_register_and_call_persistent(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(config, persistent=True)
            assert "add" in reg
            assert "echo" in reg
            assert len(reg._mcp_integrations) == 1

    @pytest.mark.asyncio
    async def test_register_non_persistent(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(config, persistent=False)
            assert "add" in reg

    @pytest.mark.asyncio
    async def test_close_cleans_up_integrations(self):
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        reg = ToolRegistry()
        await reg.register_from_mcp_async(config, persistent=True)
        assert len(reg._mcp_integrations) == 1
        await reg.close_async()
        assert len(reg._mcp_integrations) == 0


# ---------------------------------------------------------------------------
# Sync-mode persistent connection tests (issue #211)
# ---------------------------------------------------------------------------


class TestMCPConnectionManagerSyncLoop:
    """Tests for sync tool calls via the shared AsyncRuntime."""

    def test_no_per_instance_sync_loop(self):
        """MCPConnectionManager should not have per-instance sync loop state."""
        mgr = MCPConnectionManager("http://localhost:9999/mcp")
        assert not hasattr(mgr, "_sync_loop")
        assert not hasattr(mgr, "_sync_thread")

    def test_close_sync_without_prior_calls(self):
        """close_sync() should be safe when no sync calls were made."""
        mgr = MCPConnectionManager("http://localhost:9999/mcp")
        mgr.close_sync()

    def test_sync_multiple_calls_reuse_connection(self):
        """Sync tool calls should reuse the persistent connection (no reconnect)."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        mgr = MCPConnectionManager(config, persistent=True)
        try:
            r1 = mgr.call_tool_sync("add", {"a": 1, "b": 2})
            assert mgr.is_connected

            r2 = mgr.call_tool_sync("add", {"a": 10, "b": 20})
            assert mgr.is_connected

            assert json.loads(r1.content[0].text) == {"result": 3}
            assert json.loads(r2.content[0].text) == {"result": 30}
        finally:
            mgr.close_sync()

    def test_close_sync_closes_client(self):
        """close_sync() should close the MCP client connection."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        mgr = MCPConnectionManager(config, persistent=True)
        mgr.call_tool_sync("echo", {"message": "hi"})
        assert mgr.is_connected

        mgr.close_sync()
        assert not mgr.is_connected

    def test_pickling_preserves_config(self):
        """Pickle round-trip should preserve config and drop connection state."""
        import pickle

        mgr = MCPConnectionManager("http://localhost:9999/mcp")
        data = pickle.dumps(mgr)
        restored = pickle.loads(data)
        assert restored._transport == "http://localhost:9999/mcp"
        assert restored._client is None


class TestToolRegistrySyncMCPIntegration:
    """End-to-end sync-mode MCP integration tests (issue #211)."""

    def test_sync_register_and_call(self):
        """register_from_mcp + invoke should work without reconnecting."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        with ToolRegistry() as reg:
            reg.register_from_mcp(config, persistent=True)
            assert "add" in reg
            assert "echo" in reg

            r1 = reg.invoke("add", {"a": 5, "b": 3})
            r2 = reg.invoke("add", {"a": 10, "b": 1})
            assert r1 == '{"result": 8}'
            assert r2 == '{"result": 11}'

    def test_sync_register_non_persistent(self):
        """Non-persistent mode should still work in sync."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        with ToolRegistry() as reg:
            reg.register_from_mcp(config, persistent=False)
            assert "echo" in reg
            result = reg.invoke("echo", {"message": "hello"})
            assert result == "hello"

    def test_sync_multiple_registrations_shared_loop(self):
        """Multiple sequential sync registrations share one loop (#217).

        This is the exact scenario that triggered the bug:
        registering two MCP sources sequentially would fail because
        the first loop.close() poisoned anyio's process-level state.
        """
        from toolregistry._async_runtime import AsyncRuntime

        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        with ToolRegistry() as reg:
            reg.register_from_mcp(config, namespace="ns1", persistent=True)
            assert "ns1-add" in reg

            # Second registration — would CancelledError before fix.
            reg.register_from_mcp(config, namespace="ns2", persistent=True)
            assert "ns2-add" in reg

            # Both work and share the same runtime loop.
            r1 = reg.invoke("ns1-add", {"a": 1, "b": 2})
            r2 = reg.invoke("ns2-add", {"a": 3, "b": 4})
            assert r1 == '{"result": 3}'
            assert r2 == '{"result": 7}'

            loop = AsyncRuntime.get_loop()
            assert loop.is_running()

    def test_sync_close_cleans_up(self):
        """close() should clean up MCP integrations and connections."""
        config = {
            "command": sys.executable,
            "args": [_SERVER_SCRIPT, "--transport", "stdio"],
        }
        reg = ToolRegistry()
        reg.register_from_mcp(config, persistent=True)
        assert len(reg._mcp_integrations) == 1

        reg.invoke("echo", {"message": "test"})

        connections = list(reg._mcp_integrations[0]._connections)
        assert len(connections) > 0

        reg.close()
        assert len(reg._mcp_integrations) == 0
        for c in connections:
            assert not c.is_connected
