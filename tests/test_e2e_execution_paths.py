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


# ── OpenAPI through the execution stack ────────────────────────────


class TestOpenAPIExecutionStack:
    """OpenAPI tools through invoke/execute with the full backend seam.

    Uses mock httpx clients (no live server) but goes through the real
    ToolRegistry.register_from_openapi → invoke/execute_tool_calls
    pipeline, verifying that natural_backend="inline" resolves
    correctly on sync/async paths.
    """

    @staticmethod
    def _openapi_registry():
        import json as _json
        from toolregistry.integrations.openapi.integration import OpenAPIIntegration

        from tests.test_openapi_integration import (
            PETSTORE_SPEC,
            _make_config_with_mock,
            _mock_response,
        )

        def handler(request):
            if request.url.path == "/pets" and request.method == "GET":
                return _mock_response(200, [{"id": 1, "name": "Fido"}])
            if request.url.path == "/pets" and request.method == "POST":
                body = _json.loads(request.content)
                return _mock_response(201, {"id": 2, "name": body["name"]})
            return _mock_response(404)

        reg = ToolRegistry()
        config = _make_config_with_mock(handler)
        integration = OpenAPIIntegration(reg)
        integration.register_openapi_tools(config, PETSTORE_SPEC)
        return reg

    def test_sync_invoke_openapi_tool(self):
        reg = self._openapi_registry()
        r = reg.invoke("list_pets", {"limit": 10})
        assert isinstance(r, ToolCallResult)
        assert "Fido" in r.result

    @pytest.mark.asyncio
    async def test_ainvoke_openapi_tool(self):
        reg = self._openapi_registry()
        r = await reg.ainvoke("list_pets", {"limit": 5})
        assert isinstance(r, ToolCallResult)
        assert "Fido" in r.result

    def test_sync_batch_openapi_tools(self):
        reg = self._openapi_registry()
        tcs = [
            _tc("c1", "list_pets", '{"limit": 10}'),
            _tc("c2", "create_pet", '{"name": "Rex"}'),
        ]
        results = reg.execute_tool_calls(tcs)
        assert isinstance(results["c1"], ToolCallResult)
        assert isinstance(results["c2"], ToolCallResult)
        assert "Fido" in results["c1"].result
        assert "Rex" in results["c2"].result


# ── Mixed batch: MCP + native Python in one batch ──────────────────


class TestMixedBatch:
    """MCP (→thread on sync) + native Python (→process) in the same batch."""

    def test_sync_mixed_mcp_and_native(self):
        """MCP tools resolve to thread, native tools to process, same batch."""
        reg = ToolRegistry()

        def double(n: int) -> int:
            """Native Python tool."""
            return n * 2

        reg.register(double)
        reg.register_from_mcp(_stdio_config(), persistent=True)

        tcs = [
            _tc("c1", "double", '{"n": 7}'),
            _tc("c2", "add", '{"a": 10, "b": 20}'),
            _tc("c3", "echo", '{"message": "mixed"}'),
        ]
        results = reg.execute_tool_calls(tcs)

        assert results["c1"].result == "14"
        assert results["c2"].result == '{"result": 30}'
        assert results["c3"].result == "mixed"
        assert [r.id for r in results] == ["c1", "c2", "c3"]
        reg.close()

    @pytest.mark.asyncio
    async def test_async_mixed_mcp_and_native(self):
        """Async batch: MCP (inline) + native overlap under gather."""
        reg = ToolRegistry()

        async def double(n: int) -> int:
            """Native async tool."""
            return n * 2

        reg.register(double)
        await reg.register_from_mcp_async(_stdio_config(), persistent=True)

        tcs = [
            _tc("c1", "double", '{"n": 5}'),
            _tc("c2", "add", '{"a": 3, "b": 4}'),
        ]
        results = await reg.aexecute_tool_calls(tcs)

        assert results["c1"].result == "10"
        assert results["c2"].result == '{"result": 7}'
        await reg.close_async()


# ── MCP concurrent ainvoke (same connection) ───────────────────────


class TestMCPConcurrentAinvoke:
    """Multiple ainvoke on the same MCP connection overlap correctly."""

    @pytest.mark.asyncio
    async def test_concurrent_ainvoke_same_connection(self):
        async with ToolRegistry() as reg:
            await reg.register_from_mcp_async(_stdio_config(), persistent=True)

            r1, r2 = await asyncio.gather(
                reg.ainvoke("add", {"a": 1, "b": 2}),
                reg.ainvoke("add", {"a": 10, "b": 20}),
            )
            assert isinstance(r1, ToolCallResult)
            assert isinstance(r2, ToolCallResult)
            assert r1.result == '{"result": 3}'
            assert r2.result == '{"result": 30}'


# ── PTC in batch execution ─────────────────────────────────────────


class TestPTCInBatch:
    """PTC tool through execute_tool_calls (natural_backend=inline
    promoted to thread on sync path)."""

    def test_ptc_in_sync_batch(self):
        from toolregistry.runtimes import PTC_TOOL_NAME

        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add."""
            return a + b

        reg.register(add)
        reg.ptc.enable()

        tcs = [
            _tc("c1", "add", '{"a": 3, "b": 4}'),
            _tc("c2", PTC_TOOL_NAME, '{"code": "print(add(a=10, b=20))"}'),
        ]
        results = reg.execute_tool_calls(tcs)

        assert isinstance(results["c1"], ToolCallResult)
        assert results["c1"].result == "7"
        assert isinstance(results["c2"], ToolCallResult)
        assert "30" in results["c2"].result
        reg.close()


# ── Process blocked for inline tools ───────────────────────────────


class TestProcessBlockedForInlineTools:
    """execution_mode='process' is silently blocked for inline-natural
    tools (MCP, OpenAPI) — downgraded to thread to prevent deadlock.

    The live connection state serializes via cloudpickle but the worker
    process has no connection, so it would hang.  _resolve_backend
    intercepts this and routes to thread instead.
    """

    def test_invoke_force_process_mcp_goes_thread(self):
        """invoke(execution_mode='process') on MCP tool succeeds (→thread)."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)
            r = reg.invoke("echo", {"message": "safe"}, execution_mode="process")
            assert isinstance(r, ToolCallResult)
            assert r.result == "safe"

    def test_batch_force_process_mcp_goes_thread(self):
        """execute_tool_calls(execution_mode='process') on MCP tool succeeds."""
        with ToolRegistry() as reg:
            reg.register_from_mcp(_stdio_config(), persistent=True)
            tcs = [_tc("c1", "echo", '{"message": "batch safe"}')]
            results = reg.execute_tool_calls(tcs, execution_mode="process")
            assert isinstance(results["c1"], ToolCallResult)
            assert results["c1"].result == "batch safe"

    def test_resolve_backend_blocks_process_for_inline(self):
        """_resolve_backend downgrades process→thread for inline tools."""
        reg = ToolRegistry()

        def ping(x: int) -> int:
            return x

        reg.register(
            Tool.from_function(ping, metadata=ToolMetadata(natural_backend="inline"))
        )
        tool = reg.get_tool("ping")
        backend = reg._resolve_backend(tool, execution_mode="process")
        assert backend is reg._thread_backend

    def test_resolve_backend_allows_thread_for_inline(self):
        """execution_mode='thread' on inline tools is fine (no downgrade)."""
        reg = ToolRegistry()

        def ping(x: int) -> int:
            return x

        reg.register(
            Tool.from_function(ping, metadata=ToolMetadata(natural_backend="inline"))
        )
        tool = reg.get_tool("ping")
        backend = reg._resolve_backend(tool, execution_mode="thread")
        assert backend is reg._thread_backend
