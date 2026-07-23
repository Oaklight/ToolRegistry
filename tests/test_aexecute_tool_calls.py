"""Tests for aexecute_tool_calls and per-tool backend resolution in batch."""

import asyncio
import time

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry.llm.tool_calls import ErrorResult, ResultList, ToolCallResult
from toolregistry.tool import ToolMetadata


def _tc(cid: str, name: str, args: str):
    return {
        "id": cid,
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


@pytest.fixture
def registry():
    reg = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add."""
        return a + b

    def mul(a: int, b: int) -> int:
        """Multiply."""
        return a * b

    async def aslow(n: int) -> int:
        """Async slow echo."""
        await asyncio.sleep(0.2)
        return n

    reg.register(add)
    reg.register(mul)
    reg.register(aslow)
    return reg


class TestAexecuteToolCalls:
    @pytest.mark.asyncio
    async def test_basic_batch(self, registry):
        tcs = [
            _tc("c1", "add", '{"a": 2, "b": 3}'),
            _tc("c2", "mul", '{"a": 4, "b": 5}'),
        ]
        r = await registry.aexecute_tool_calls(tcs)
        assert isinstance(r, ResultList)
        assert r["c1"].result == "5"
        assert r["c2"].result == "20"

    @pytest.mark.asyncio
    async def test_ordering_preserved(self, registry):
        tcs = [
            _tc("c1", "add", '{"a": 1, "b": 1}'),
            _tc("c2", "mul", '{"a": 2, "b": 3}'),
            _tc("c3", "add", '{"a": 5, "b": 5}'),
        ]
        r = await registry.aexecute_tool_calls(tcs)
        assert [x.id for x in r] == ["c1", "c2", "c3"]

    @pytest.mark.asyncio
    async def test_async_tools_overlap(self, registry):
        """Two 0.2s async tools should overlap under gather (~0.2s not 0.4s)."""
        tcs = [
            _tc("c1", "aslow", '{"n": 1}'),
            _tc("c2", "aslow", '{"n": 2}'),
        ]
        start = time.perf_counter()
        r = await registry.aexecute_tool_calls(tcs)
        elapsed = time.perf_counter() - start
        assert {x.result for x in r} == {"1", "2"}
        assert elapsed < 0.35

    @pytest.mark.asyncio
    async def test_tool_error_is_error_result(self, registry):
        def boom(x: int) -> int:
            raise ValueError("broken")

        registry.register(boom)
        tcs = [
            _tc("c1", "add", '{"a": 1, "b": 2}'),
            _tc("c2", "boom", '{"x": 1}'),
        ]
        r = await registry.aexecute_tool_calls(tcs)
        assert isinstance(r["c1"], ToolCallResult)
        assert isinstance(r["c2"], ErrorResult)
        assert "broken" in r["c2"].message

    @pytest.mark.asyncio
    async def test_disabled_tool_is_error_result(self, registry):
        registry.disable("mul", reason="maint")
        tcs = [
            _tc("c1", "add", '{"a": 1, "b": 2}'),
            _tc("c2", "mul", '{"a": 2, "b": 3}'),
        ]
        r = await registry.aexecute_tool_calls(tcs)
        assert isinstance(r["c1"], ToolCallResult)
        assert isinstance(r["c2"], ErrorResult)

    @pytest.mark.asyncio
    async def test_concurrency_unsafe_runs_sequentially(self, registry):
        """An unsafe tool forces the whole batch onto the sequential path.

        Uses async inline tools so timing is observable: under the
        sequential path two 0.2s sleeps take ~0.4s (no overlap), versus
        ~0.2s if they had been gathered.
        """

        async def slow_unsafe(n: int) -> int:
            await asyncio.sleep(0.2)
            return n

        async def slow_safe(n: int) -> int:
            await asyncio.sleep(0.2)
            return n

        registry.register(
            Tool.from_function(
                slow_unsafe, metadata=ToolMetadata(is_concurrency_safe=False)
            )
        )
        registry.register(slow_safe)

        tcs = [
            _tc("c1", "slow_unsafe", '{"n": 1}'),
            _tc("c2", "slow_safe", '{"n": 2}'),
        ]
        start = time.perf_counter()
        r = await registry.aexecute_tool_calls(tcs)
        elapsed = time.perf_counter() - start

        assert r["c1"].result == "1"
        assert r["c2"].result == "2"
        # Sequential (no gather): the two 0.2s sleeps do not overlap.
        assert elapsed >= 0.4


class TestBatchBackendResolution:
    """Per-tool backend resolution in execute_tool_calls (sync)."""

    def test_mixed_inline_and_pool(self, registry):
        # ping resolves to inline (like MCP/OpenAPI); add uses batch default.
        def ping(x: int) -> int:
            """Ping."""
            return x

        registry.register(
            Tool.from_function(ping, metadata=ToolMetadata(natural_backend="inline"))
        )
        tcs = [
            _tc("c1", "add", '{"a": 1, "b": 1}'),
            _tc("c2", "ping", '{"x": 9}'),
        ]
        r = registry.execute_tool_calls(tcs)
        assert r["c1"].result == "2"
        assert r["c2"].result == "9"
        assert [x.id for x in r] == ["c1", "c2"]

    def test_execution_mode_override(self, registry):
        tcs = [_tc("c1", "add", '{"a": 3, "b": 4}')]
        r = registry.execute_tool_calls(tcs, execution_mode="thread")
        assert r["c1"].result == "7"

    def test_inline_natural_backend_resolves_inline(self, registry):
        def ping(x: int) -> int:
            """Ping."""
            return x

        registry.register(
            Tool.from_function(ping, metadata=ToolMetadata(natural_backend="inline"))
        )
        tool = registry.get_tool("ping")
        # batch default is process, but natural_backend wins.
        backend = registry._resolve_backend(
            tool, None, default=registry._execution_mode
        )
        assert backend is registry._inline_backend

    def test_plain_tool_uses_batch_default(self, registry):
        tool = registry.get_tool("add")
        backend = registry._resolve_backend(
            tool, None, default=registry._execution_mode
        )
        # default execution mode is process
        assert backend is registry._process_backend
