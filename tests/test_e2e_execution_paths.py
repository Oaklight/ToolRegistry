"""End-to-end tests for the execution stack with real MCP tools.

Verifies that sync/async registration, sync/async single-call, and
sync/async batch execution all work with a live MCP stdio server —
not just mock functions. Also tests that per-tool timeout is enforced
on every path where it should be.
"""

import asyncio
import sys
import time
from pathlib import Path

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry.llm.tool_calls import ErrorResult, ToolCallResult
from toolregistry.tool import ToolMetadata

_SERVER_SCRIPT = str(Path(__file__).parent / "_mcp_test_server.py")


def _stdio_config():
    return {
        "command": sys.executable,
        "args": [_SERVER_SCRIPT, "--transport", "stdio"],
    }


def _tc(cid: str, name: str, args: str):
    return {
        "id": cid,
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


# ── Sync registration + sync invoke ─────────────────────────────────


class TestSyncMCPPaths:
    def test_sync_register_and_invoke(self):
        """register_from_mcp (sync) + invoke (sync) with a real MCP tool."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)
            assert "add" in reg

            r = reg.invoke("add", {"a": 10, "b": 20})
            assert isinstance(r, ToolCallResult)
            assert r.result == '{"result": 30}'

    def test_sync_register_and_invoke_echo(self):
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)
            r = reg.invoke("echo", {"message": "hello world"})
            assert isinstance(r, ToolCallResult)
            assert r.result == "hello world"

    def test_sync_register_and_execute_batch(self):
        """register_from_mcp (sync) + execute_tool_calls (sync batch)."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)

            tcs = [
                _tc("c1", "add", '{"a": 1, "b": 2}'),
                _tc("c2", "echo", '{"message": "hi"}'),
                _tc("c3", "greet", '{"name": "Alice"}'),
            ]
            results = reg.execute_tool_calls(tcs)
            assert results["c1"].result == '{"result": 3}'
            assert results["c2"].result == "hi"
            assert "Alice" in results["c3"].result
            assert [r.id for r in results] == ["c1", "c2", "c3"]


# ── Async registration + async invoke ───────────────────────────────


class TestAsyncMCPPaths:
    @pytest.mark.asyncio
    async def test_async_register_and_ainvoke(self):
        """register_from_mcp_async + ainvoke with a real MCP tool."""
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(_stdio_config(), persistent=True)
            assert "add" in reg

            r = await reg.ainvoke("add", {"a": 5, "b": 7})
            assert isinstance(r, ToolCallResult)
            assert r.result == '{"result": 12}'

    @pytest.mark.asyncio
    async def test_async_register_and_aexecute_batch(self):
        """register_from_mcp_async + aexecute_tool_calls."""
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(_stdio_config(), persistent=True)

            tcs = [
                _tc("c1", "add", '{"a": 3, "b": 4}'),
                _tc("c2", "echo", '{"message": "async"}'),
            ]
            results = await reg.aexecute_tool_calls(tcs)
            assert results["c1"].result == '{"result": 7}'
            assert results["c2"].result == "async"


# ── Mixed: sync register + async invoke ─────────────────────────────


class TestMixedPaths:
    @pytest.mark.asyncio
    async def test_sync_register_async_invoke(self):
        """register_from_mcp (sync) + ainvoke (async)."""
        reg = ToolRegistry()
        reg.register_from_mcp(_stdio_config(), persistent=True)
        try:
            r = await reg.ainvoke("add", {"a": 100, "b": 200})
            assert isinstance(r, ToolCallResult)
            assert r.result == '{"result": 300}'
        finally:
            await reg.close_async()

    def test_sync_register_sync_invoke_multiple_sources(self):
        """Two MCP sources registered sync, both callable via sync invoke."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), namespace="src1", persistent=True)
            reg.register_from_mcp(_stdio_config(), namespace="src2", persistent=True)
            assert "src1-add" in reg
            assert "src2-add" in reg

            r1 = reg.invoke("src1-add", {"a": 1, "b": 2})
            r2 = reg.invoke("src2-echo", {"message": "test"})
            assert isinstance(r1, ToolCallResult)
            assert isinstance(r2, ToolCallResult)


# ── Timeout enforcement ─────────────────────────────────────────────


class TestTimeoutEnforcement:
    def test_sync_invoke_native_tool_timeout(self):
        """sync invoke + native async tool with tight timeout → ErrorResult."""
        reg = ToolRegistry()

        async def slow(n: int) -> int:
            await asyncio.sleep(5)
            return n

        reg.register(Tool.from_function(slow, metadata=ToolMetadata(timeout=0.3)))

        start = time.perf_counter()
        r = reg.invoke("slow", {"n": 1})
        elapsed = time.perf_counter() - start

        assert isinstance(r, ErrorResult)
        assert "timed out" in r.message
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_ainvoke_native_tool_timeout(self):
        """ainvoke + native async tool with tight timeout → ErrorResult."""
        reg = ToolRegistry()

        async def slow(n: int) -> int:
            await asyncio.sleep(5)
            return n

        reg.register(Tool.from_function(slow, metadata=ToolMetadata(timeout=0.3)))

        start = time.perf_counter()
        r = await reg.ainvoke("slow", {"n": 1})
        elapsed = time.perf_counter() - start

        assert isinstance(r, ErrorResult)
        assert "timed out" in r.message
        assert elapsed < 2.0

    def test_sync_batch_native_tool_timeout(self):
        """execute_tool_calls with a native tool that times out."""
        reg = ToolRegistry()

        async def slow(n: int) -> int:
            await asyncio.sleep(5)
            return n

        def fast(n: int) -> int:
            return n * 2

        reg.register(fast)
        reg.register(Tool.from_function(slow, metadata=ToolMetadata(timeout=0.3)))

        tcs = [
            _tc("c1", "fast", '{"n": 5}'),
            _tc("c2", "slow", '{"n": 1}'),
        ]
        start = time.perf_counter()
        results = reg.execute_tool_calls(tcs)
        elapsed = time.perf_counter() - start

        assert isinstance(results["c1"], ToolCallResult)
        assert results["c1"].result == "10"
        assert isinstance(results["c2"], ErrorResult)
        assert "timed out" in results["c2"].message
        assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_async_batch_native_tool_timeout(self):
        """aexecute_tool_calls with a native tool that times out."""
        reg = ToolRegistry()

        async def slow(n: int) -> int:
            await asyncio.sleep(5)
            return n

        def fast(n: int) -> int:
            return n * 2

        reg.register(fast)
        reg.register(Tool.from_function(slow, metadata=ToolMetadata(timeout=0.3)))

        tcs = [
            _tc("c1", "fast", '{"n": 5}'),
            _tc("c2", "slow", '{"n": 1}'),
        ]
        start = time.perf_counter()
        results = await reg.aexecute_tool_calls(tcs)
        elapsed = time.perf_counter() - start

        assert isinstance(results["c1"], ToolCallResult)
        assert results["c1"].result == "10"
        assert isinstance(results["c2"], ErrorResult)
        assert "timed out" in results["c2"].message
        assert elapsed < 2.0


# ── Real MCP tool timeout ──────────────────────────────────────────


class TestMCPToolTimeout:
    """Timeout with a real MCP server tool (not a mock async function).

    Uses ``slow_tool`` from the test MCP server which does a real
    ``time.sleep`` in the subprocess, exercising the full MCP transport
    path (stdio pipes, MCP SDK request/response, connection manager).
    """

    def test_sync_invoke_mcp_timeout(self):
        """sync invoke + real MCP tool + timeout → ErrorResult."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)
            tool = reg.get_tool("slow_tool")
            tool.metadata.timeout = 0.5

            start = time.perf_counter()
            r = reg.invoke("slow_tool", {"seconds": 5.0})
            elapsed = time.perf_counter() - start

            assert isinstance(r, ErrorResult)
            assert "timed out" in r.message
            assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_ainvoke_mcp_timeout(self):
        """ainvoke + real MCP tool + timeout → ErrorResult."""
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(_stdio_config(), persistent=True)
            tool = reg.get_tool("slow_tool")
            tool.metadata.timeout = 0.5

            start = time.perf_counter()
            r = await reg.ainvoke("slow_tool", {"seconds": 5.0})
            elapsed = time.perf_counter() - start

            assert isinstance(r, ErrorResult)
            assert "timed out" in r.message
            assert elapsed < 2.0

    def test_sync_invoke_mcp_no_timeout_completes(self):
        """MCP tool without timeout runs to completion normally."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)

            r = reg.invoke("slow_tool", {"seconds": 0.3})
            assert isinstance(r, ToolCallResult)
            assert "slept" in r.result

    def test_sync_batch_mcp_timeout(self):
        """sync batch: single slow MCP tool times out.

        Uses a single-tool batch because our test MCP server uses
        blocking ``time.sleep`` in ``slow_tool``, which serializes all
        requests at the server process level.  This is a test-server
        limitation, not an MCP protocol constraint — the protocol
        multiplexes by request-id and our client-side connection
        manager does not serialize calls.
        """
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)
            tool = reg.get_tool("slow_tool")
            tool.metadata.timeout = 0.5

            tcs = [_tc("c1", "slow_tool", '{"seconds": 5.0}')]
            start = time.perf_counter()
            results = reg.execute_tool_calls(tcs)
            elapsed = time.perf_counter() - start

            assert isinstance(results["c1"], ErrorResult)
            assert "timed out" in results["c1"].message
            assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_async_batch_mcp_timeout(self):
        """async batch: single slow MCP tool times out."""
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(_stdio_config(), persistent=True)
            tool = reg.get_tool("slow_tool")
            tool.metadata.timeout = 0.5

            tcs = [_tc("c1", "slow_tool", '{"seconds": 5.0}')]
            start = time.perf_counter()
            results = await reg.aexecute_tool_calls(tcs)
            elapsed = time.perf_counter() - start

            assert isinstance(results["c1"], ErrorResult)
            assert "timed out" in results["c1"].message
            assert elapsed < 2.0
