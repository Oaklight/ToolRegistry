"""Regression tests for #314.

``asyncio.iscoroutinefunction`` is deprecated on Python 3.14 and removed in
3.16.  Both executor backends must use ``inspect.iscoroutinefunction`` so a
``-W error`` user can still execute tools.
"""

import asyncio

import pytest

from toolregistry.executor import ProcessPoolBackend, ThreadBackend


def _add(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y


@pytest.mark.parametrize("backend_cls", [ThreadBackend, ProcessPoolBackend])
def test_submit_does_not_call_asyncio_iscoroutinefunction(monkeypatch, backend_cls):
    def _deprecated(*args, **kwargs):
        raise AssertionError("asyncio.iscoroutinefunction must not be used")

    monkeypatch.setattr(asyncio, "iscoroutinefunction", _deprecated)

    backend = backend_cls(max_workers=1)
    try:
        handle = backend.submit(_add, {"x": 1, "y": 2})
        assert handle.result(timeout=10) == 3
    finally:
        backend.shutdown()
