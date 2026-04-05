"""Tests for BaseToolWrapper ABC."""

import asyncio
from typing import Any

import pytest

from toolregistry.tool_wrapper import BaseToolWrapper


# ---------------------------------------------------------------------------
# Concrete subclass for testing
# ---------------------------------------------------------------------------


class ConcreteWrapper(BaseToolWrapper):
    """Concrete implementation of BaseToolWrapper for testing."""

    def __init__(
        self, name="test_wrapper", params=None, sync_result=None, async_result=None
    ):
        super().__init__(name=name, params=params)
        self._sync_result = sync_result or "sync_result"
        self._async_result = async_result or "async_result"

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        kwargs = self._process_args(*args, **kwargs)
        return {"result": self._sync_result, "kwargs": kwargs}

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        kwargs = self._process_args(*args, **kwargs)
        return {"result": self._async_result, "kwargs": kwargs}


class FailingWrapper(BaseToolWrapper):
    """Wrapper that raises exceptions."""

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("sync error")

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("async error")


# ===========================================================================
# TestProcessArgs
# ===========================================================================


class TestProcessArgs:
    """Tests for BaseToolWrapper._process_args()."""

    def test_kwargs_passthrough(self):
        """Keyword arguments pass through unchanged."""
        wrapper = ConcreteWrapper(params=["a", "b"])
        result = wrapper._process_args(a=1, b=2)
        assert result == {"a": 1, "b": 2}

    def test_positional_args_mapped(self):
        """Positional args are mapped to param names."""
        wrapper = ConcreteWrapper(params=["x", "y"])
        result = wrapper._process_args(10, 20)
        assert result == {"x": 10, "y": 20}

    def test_mixed_args(self):
        """Positional and keyword args together."""
        wrapper = ConcreteWrapper(params=["a", "b", "c"])
        result = wrapper._process_args(1, c=3)
        assert result == {"a": 1, "c": 3}

    def test_no_args(self):
        """No arguments returns empty dict."""
        wrapper = ConcreteWrapper(params=["a"])
        result = wrapper._process_args()
        assert result == {}

    def test_positional_without_params_raises(self):
        """Positional args without params definition raises ValueError."""
        wrapper = ConcreteWrapper(params=None)
        with pytest.raises(ValueError, match="not initialized"):
            wrapper._process_args(1, 2)

    def test_too_many_positional_raises(self):
        """Too many positional args raises TypeError."""
        wrapper = ConcreteWrapper(params=["a"])
        with pytest.raises(TypeError, match="at most 1"):
            wrapper._process_args(1, 2)

    def test_duplicate_arg_raises(self):
        """Positional + keyword for same param raises TypeError."""
        wrapper = ConcreteWrapper(params=["a", "b"])
        with pytest.raises(TypeError, match="both a positional and a keyword"):
            wrapper._process_args(1, a=10)

    def test_empty_params_no_args(self):
        """Empty params list with no args works."""
        wrapper = ConcreteWrapper(params=[])
        result = wrapper._process_args()
        assert result == {}


# ===========================================================================
# TestCallDispatch
# ===========================================================================


class TestCallDispatch:
    """Tests for BaseToolWrapper.__call__() dispatch."""

    def test_sync_context_calls_sync(self):
        """In sync context, __call__ returns call_sync result."""
        wrapper = ConcreteWrapper(
            params=["a"], sync_result="from_sync", async_result="from_async"
        )
        result = wrapper(a=42)
        assert result["result"] == "from_sync"
        assert result["kwargs"] == {"a": 42}

    @pytest.mark.asyncio
    async def test_async_context_calls_async(self):
        """In async context, __call__ returns a coroutine from call_async."""
        wrapper = ConcreteWrapper(
            params=["a"], sync_result="from_sync", async_result="from_async"
        )
        result = wrapper(a=42)
        # In async context, __call__ returns a coroutine
        if asyncio.iscoroutine(result):
            result = await result
        assert result["result"] == "from_async"

    def test_sync_exception_propagates(self):
        """Exceptions from call_sync propagate through __call__."""
        wrapper = FailingWrapper(name="fail")
        with pytest.raises(RuntimeError, match="sync error"):
            wrapper()

    @pytest.mark.asyncio
    async def test_async_exception_propagates(self):
        """Exceptions from call_async propagate through __call__."""
        wrapper = FailingWrapper(name="fail")
        result = wrapper()
        if asyncio.iscoroutine(result):
            with pytest.raises(RuntimeError, match="async error"):
                await result


# ===========================================================================
# TestWrapperProtocol
# ===========================================================================


class TestWrapperProtocol:
    """Tests for BaseToolWrapper as ABC."""

    def test_cannot_instantiate_abc(self):
        """Cannot directly instantiate BaseToolWrapper."""
        with pytest.raises(TypeError):
            BaseToolWrapper(name="test")

    def test_incomplete_subclass_raises(self):
        """Subclass without call_sync/call_async cannot be instantiated."""

        class IncompleteWrapper(BaseToolWrapper):
            def call_sync(self, *args, **kwargs):
                pass

        with pytest.raises(TypeError):
            IncompleteWrapper(name="test")

    def test_name_stored(self):
        """Name is stored correctly."""
        wrapper = ConcreteWrapper(name="my_tool")
        assert wrapper.name == "my_tool"

    def test_params_stored(self):
        """Params are stored correctly."""
        wrapper = ConcreteWrapper(params=["x", "y", "z"])
        assert wrapper.params == ["x", "y", "z"]

    def test_params_default_none(self):
        """Params default to None."""
        wrapper = ConcreteWrapper()
        assert wrapper.params is None
