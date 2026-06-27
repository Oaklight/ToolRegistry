"""Tests for the PTC protocols and DirectProjection (runtimes subpackage)."""

import asyncio

import pytest

from toolregistry.runtimes import (
    CodeResult,
    CodeRuntime,
    DirectProjection,
    ToolProjection,
)


# ---------------------------------------------------------------------------
# CodeResult
# ---------------------------------------------------------------------------


class TestCodeResult:
    def test_defaults(self):
        r = CodeResult()
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.return_code == 0
        assert r.error is None

    def test_success(self):
        r = CodeResult(stdout="hello\n", return_code=0)
        assert r.stdout == "hello\n"
        assert r.return_code == 0

    def test_failure(self):
        r = CodeResult(stderr="warn", return_code=1, error="ZeroDivisionError")
        assert r.return_code == 1
        assert r.error == "ZeroDivisionError"

    def test_frozen(self):
        r = CodeResult()
        with pytest.raises(AttributeError):
            r.stdout = "mutate"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolProjection protocol
# ---------------------------------------------------------------------------


class TestToolProjection:
    def test_runtime_checkable(self):
        assert isinstance(DirectProjection(name="t", fn=lambda: None), ToolProjection)

    def test_custom_class_satisfies_protocol(self):
        class MyProjection:
            @property
            def name(self) -> str:
                return "custom"

            @property
            def doc(self) -> str | None:
                return "doc"

            def __call__(self, **kwargs):
                return kwargs

        assert isinstance(MyProjection(), ToolProjection)


# ---------------------------------------------------------------------------
# DirectProjection
# ---------------------------------------------------------------------------


class TestDirectProjection:
    def test_sync_callable(self):
        def add(a: int, b: int) -> int:
            return a + b

        proj = DirectProjection(name="add", fn=add, doc="Add two numbers.")
        assert proj.name == "add"
        assert proj.doc == "Add two numbers."
        assert proj(a=3, b=4) == 7

    def test_async_callable(self):
        async def multiply(a: int, b: int) -> int:
            return a * b

        proj = DirectProjection(name="multiply", fn=multiply)
        assert proj.name == "multiply"
        assert proj.doc is None
        # call_sync dispatches async via asyncio.run
        assert proj(a=3, b=5) == 15

    def test_fn_attribute(self):
        def f():
            pass

        proj = DirectProjection(name="f", fn=f)
        assert proj.fn is f

    def test_no_doc(self):
        proj = DirectProjection(name="t", fn=lambda: 42)
        assert proj.doc is None
        assert proj() == 42


# ---------------------------------------------------------------------------
# CodeRuntime protocol
# ---------------------------------------------------------------------------


class TestCodeRuntime:
    def test_runtime_checkable(self):
        class MockRuntime:
            async def execute(
                self,
                code,
                namespace,
                *,
                timeout=None,
                extra_globals=None,
            ):
                return CodeResult(stdout="ok")

        assert isinstance(MockRuntime(), CodeRuntime)

    def test_mock_runtime_executes(self):
        class MockRuntime:
            async def execute(
                self, code, namespace, *, timeout=None, extra_globals=None
            ):
                # Simulate executing code that calls a tool
                tool = namespace.get("add")
                if tool:
                    result = tool(a=1, b=2)
                    return CodeResult(stdout=str(result), return_code=0)
                return CodeResult(return_code=1, error="no tool")

        runtime = MockRuntime()
        add_proj = DirectProjection(
            name="add", fn=lambda a, b: a + b, doc="Add numbers"
        )
        ns = {"add": add_proj}

        result = asyncio.run(runtime.execute("", ns))
        assert result.stdout == "3"
        assert result.return_code == 0
