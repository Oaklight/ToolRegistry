"""Tests for ToolRegistry.ainvoke() and async permission resolution."""

import asyncio
import threading

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry.llm.tool_calls import ErrorResult, ToolCallResult
from toolregistry.permissions import (
    PermissionPolicy,
    PermissionRequest,
    PermissionResult,
    PermissionRule,
)
from toolregistry.tool import ToolMetadata, ToolTag


class TestAinvoke:
    @pytest.mark.asyncio
    async def test_ainvoke_sync_tool(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add."""
            return a + b

        reg.register(add)
        result = await reg.ainvoke("add", {"a": 3, "b": 4})
        assert isinstance(result, ToolCallResult)
        assert result.result == "7"

    @pytest.mark.asyncio
    async def test_ainvoke_async_tool(self):
        reg = ToolRegistry()

        async def amul(a: int, b: int) -> int:
            """Multiply async."""
            return a * b

        reg.register(amul)
        result = await reg.ainvoke("amul", {"a": 3, "b": 4})
        assert isinstance(result, ToolCallResult)
        assert result.result == "12"

    @pytest.mark.asyncio
    async def test_ainvoke_nonexistent_returns_error(self):
        reg = ToolRegistry()
        result = await reg.ainvoke("nope", {})
        assert isinstance(result, ErrorResult)
        assert "not registered" in result.message

    @pytest.mark.asyncio
    async def test_ainvoke_disabled_returns_error(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        reg.disable("add", reason="maint")
        result = await reg.ainvoke("add", {"a": 1, "b": 2})
        assert isinstance(result, ErrorResult)
        assert "disabled" in result.message

    @pytest.mark.asyncio
    async def test_ainvoke_tool_error_returns_error(self):
        reg = ToolRegistry()

        def failing(x: int) -> int:
            raise ValueError("broken")

        reg.register(failing)
        result = await reg.ainvoke("failing", {"x": 1})
        assert isinstance(result, ErrorResult)
        assert "broken" in result.message

    @pytest.mark.asyncio
    async def test_ainvoke_does_not_block_loop(self):
        """Concurrent ainvoke of async tools overlap on the loop."""
        reg = ToolRegistry()

        async def slow(n: int) -> int:
            await asyncio.sleep(0.2)
            return n

        reg.register(slow)

        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            reg.ainvoke("slow", {"n": 1}),
            reg.ainvoke("slow", {"n": 2}),
        )
        elapsed = asyncio.get_event_loop().time() - start

        assert {r.result for r in results} == {"1", "2"}
        # Concurrent: well under the 0.4s serial lower bound.
        assert elapsed < 0.35


class TestBackendResolution:
    def test_inline_default_for_native(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        tool = reg.get_tool("add")
        assert reg._resolve_backend(tool) is reg._inline_backend

    def test_execution_mode_override(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        reg.register(add)
        tool = reg.get_tool("add")
        assert reg._resolve_backend(tool, "thread") is reg._thread_backend
        assert reg._resolve_backend(tool, "process") is reg._process_backend

    def test_natural_backend_hint(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        tool = Tool.from_function(add, metadata=ToolMetadata(natural_backend="thread"))
        reg.register(tool)
        resolved = reg.get_tool("add")
        assert reg._resolve_backend(resolved) is reg._thread_backend

    def test_override_beats_natural_backend(self):
        reg = ToolRegistry()

        def add(a: int, b: int) -> int:
            return a + b

        tool = Tool.from_function(add, metadata=ToolMetadata(natural_backend="thread"))
        reg.register(tool)
        resolved = reg.get_tool("add")
        assert reg._resolve_backend(resolved, "process") is reg._process_backend


class TestAsyncPermission:
    @pytest.mark.asyncio
    async def test_async_handler_resolved_without_thread_bridge(self):
        """ainvoke awaits an async permission handler on the caller loop.

        The handler records the thread it runs on; it must be the same
        thread as the test (no ThreadPoolExecutor bridge).
        """
        reg = ToolRegistry()

        def dangerous(cmd: str) -> str:
            return cmd

        tool = Tool.from_function(
            dangerous, metadata=ToolMetadata(tags={ToolTag.DESTRUCTIVE})
        )
        reg.register(tool)

        ask_rule = PermissionRule(
            name="ask_destructive",
            match=lambda t, p: ToolTag.DESTRUCTIVE in t.metadata.tags,
            result=PermissionResult.ASK,
            reason="confirm",
        )

        handler_thread: dict[str, int] = {}

        class AllowHandler:
            async def handle(self, request: PermissionRequest) -> PermissionResult:
                handler_thread["id"] = threading.get_ident()
                return PermissionResult.ALLOW

        reg.set_permission_policy(
            PermissionPolicy(rules=[ask_rule], handler=AllowHandler())
        )

        result = await reg.ainvoke("dangerous", {"cmd": "ls"})
        assert isinstance(result, ToolCallResult)
        assert result.result == "ls"
        assert handler_thread["id"] == threading.get_ident()

    @pytest.mark.asyncio
    async def test_async_handler_deny_returns_error(self):
        reg = ToolRegistry()

        def dangerous(cmd: str) -> str:
            return cmd

        tool = Tool.from_function(
            dangerous, metadata=ToolMetadata(tags={ToolTag.DESTRUCTIVE})
        )
        reg.register(tool)

        ask_rule = PermissionRule(
            name="ask_destructive",
            match=lambda t, p: ToolTag.DESTRUCTIVE in t.metadata.tags,
            result=PermissionResult.ASK,
            reason="confirm",
        )

        class DenyHandler:
            async def handle(self, request: PermissionRequest) -> PermissionResult:
                return PermissionResult.DENY

        reg.set_permission_policy(
            PermissionPolicy(rules=[ask_rule], handler=DenyHandler())
        )

        result = await reg.ainvoke("dangerous", {"cmd": "rm -rf /"})
        assert isinstance(result, ErrorResult)
        assert "denied" in result.message
