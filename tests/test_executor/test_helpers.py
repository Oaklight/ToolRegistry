"""Tests for executor helper functions."""

from toolregistry.executor import ExecutionContext
from toolregistry.executor._helpers import make_sync_wrapper, should_inject_context


class TestMakeSyncWrapper:
    def test_wraps_async_function(self):
        async def add(x: int, y: int) -> int:
            return x + y

        sync_add = make_sync_wrapper(add)
        assert sync_add(x=3, y=4) == 7

    def test_preserves_arguments(self):
        async def greet(name: str) -> str:
            return f"hello {name}"

        sync_greet = make_sync_wrapper(greet)
        assert sync_greet(name="world") == "hello world"


class TestShouldInjectContext:
    def test_typed_ctx_parameter(self):
        def f(x: int, _ctx: ExecutionContext) -> None:
            pass

        assert should_inject_context(f) is True

    def test_untyped_ctx_parameter(self):
        def f(_ctx) -> None:
            pass

        assert should_inject_context(f) is True

    def test_no_ctx_parameter(self):
        def f(x: int) -> None:
            pass

        assert should_inject_context(f) is False

    def test_wrong_name(self):
        def f(ctx: ExecutionContext) -> None:
            pass

        assert should_inject_context(f) is False

    def test_no_params(self):
        def f() -> None:
            pass

        assert should_inject_context(f) is False

    def test_ctx_as_optional(self):
        def f(x: int, _ctx: ExecutionContext | None = None) -> None:
            pass

        # _ctx exists but annotation is Optional, not exactly ExecutionContext
        # should still match by name
        assert should_inject_context(f) is False
