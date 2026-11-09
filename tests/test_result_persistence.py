"""Paged persistence of large tool results (#418 L4)."""

import json
import os
import re
import stat
from concurrent.futures import ThreadPoolExecutor

import pytest

from toolregistry import Tool, ToolMetadata, ToolRegistry
from toolregistry.llm.truncation import (
    ResultStore,
    default_result_store,
)

_RESULT_ID = re.compile(r"res_[0-9a-f]{12}")


def _make_registry(**kwargs):
    """Build a registry with persistence and one tool that returns 400 chars."""
    registry = ToolRegistry(persist_large_results=True, **kwargs)

    def big(n: int = 400) -> str:
        """Return a large string."""
        return "x" * n

    registry.register(
        Tool.from_function(big, metadata=ToolMetadata(max_result_size=50))
    )
    return registry


def _call_big(registry, n: int = 400) -> str:
    """Run ``big`` through execute_tool_calls and return the result text."""
    calls = [
        {
            "id": "call_big",
            "type": "function",
            "function": {"name": "big", "arguments": json.dumps({"n": n})},
        }
    ]
    return registry.execute_tool_calls(calls)["call_big"].result


def _result_id(text: str) -> str:
    """Extract the opaque result id from a truncation header."""
    match = _RESULT_ID.search(text)
    assert match is not None, text
    return match.group(0)


class TestDefaultWritesNothing:
    def test_default_registry_stores_no_result(self, monkeypatch):
        """Without the opt-in flag the full result never reaches disk."""
        registry = ToolRegistry(default_max_result_size=50)

        def big(n: int = 400) -> str:
            """Return a large string."""
            return "x" * n

        registry.register(big)

        def fail(*args, **kwargs):
            raise AssertionError("ResultStore.put must not be called")

        monkeypatch.setattr(ResultStore, "put", fail)

        result = _call_big(registry)

        assert "Truncated" in result
        assert "full output" not in result
        assert "res_" not in result
        assert registry._result_store is None

    def test_read_result_is_absent_by_default(self):
        assert "read_result" not in ToolRegistry()

    def test_read_result_is_registered_when_enabled(self):
        registry = ToolRegistry(persist_large_results=True)
        assert "read_result" in registry
        assert registry._result_store is not None


class TestStoredResults:
    def test_stored_file_is_private(self):
        registry = _make_registry()
        result = _call_big(registry)
        result_id = _result_id(result)

        store = registry._result_store
        path = store.path_for(result_id)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(store.root).st_mode) == 0o700

    def test_header_names_the_id_and_never_the_path(self):
        registry = _make_registry()
        result = _call_big(registry)
        result_id = _result_id(result)

        assert f"full output: {result_id} (read it with read_result)" in result
        assert registry._result_store.root not in result
        assert registry._result_store.path_for(result_id) not in result

    def test_read_result_pages_through_the_full_output(self):
        registry = _make_registry()
        result_id = _result_id(_call_big(registry))

        pages = []
        offset = 0
        while True:
            page = registry.read_result(result_id, offset=offset, limit=100)
            pages.append(page)
            if len(page) < 100:
                break
            offset += 100

        assert "".join(pages) == "x" * 400

    def test_read_result_tool_is_callable(self):
        registry = _make_registry()
        result_id = _result_id(_call_big(registry))
        calls = [
            {
                "id": "call_read",
                "type": "function",
                "function": {
                    "name": "read_result",
                    "arguments": json.dumps(
                        {"id": result_id, "offset": 10, "limit": 5}
                    ),
                },
            }
        ]

        assert registry.execute_tool_calls(calls)["call_read"].result == "xxxxx"

    def test_unknown_id_is_refused(self):
        registry = _make_registry()
        with pytest.raises(ValueError, match="unknown result id"):
            registry.read_result("res_000000000000")

    @pytest.mark.parametrize(
        "bad_id",
        [
            "res_../../etc/passwd",
            "../../etc/passwd",
            "res_0123456789AB",
            "res_0123456789a",
            "",
        ],
    )
    def test_invalid_ids_are_refused(self, bad_id):
        registry = _make_registry()
        with pytest.raises(ValueError, match="invalid result id"):
            registry.read_result(bad_id)

    @pytest.mark.parametrize("kwargs", [{"offset": -1}, {"limit": -1}])
    def test_negative_slices_are_refused(self, kwargs):
        registry = _make_registry()
        result_id = _result_id(_call_big(registry))
        with pytest.raises(ValueError, match="non-negative integer"):
            registry.read_result(result_id, **kwargs)

    def test_read_result_requires_the_flag(self):
        registry = ToolRegistry()
        with pytest.raises(RuntimeError, match="not enabled"):
            registry.read_result("res_000000000000")


class TestRetention:
    def test_expired_result_cannot_be_read(self, tmp_path):
        now = [1000.0]
        store = ResultStore(root=str(tmp_path), ttl=60, clock=lambda: now[0])
        result_id, path = store.put("hello")

        assert store.read(result_id) == "hello"

        now[0] += 61
        with pytest.raises(ValueError, match="expired"):
            store.read(result_id)
        assert not os.path.exists(path)

    def test_cleanup_on_write_removes_expired_files(self, tmp_path):
        now = [1000.0]
        store = ResultStore(root=str(tmp_path), ttl=60, clock=lambda: now[0])
        old_id, old_path = store.put("old")

        now[0] += 61
        store.put("new")

        assert not os.path.exists(old_path)
        with pytest.raises(ValueError, match="unknown result id"):
            store.read(old_id)

    def test_quota_evicts_the_oldest_file(self, tmp_path):
        now = [1000.0]
        store = ResultStore(root=str(tmp_path), quota=10, clock=lambda: now[0])
        first_id, first_path = store.put("a" * 8)

        now[0] += 1
        second_id, second_path = store.put("b" * 8)

        assert not os.path.exists(first_path)
        assert os.path.exists(second_path)
        assert store.read(second_id) == "b" * 8
        with pytest.raises(ValueError, match="unknown result id"):
            store.read(first_id)

    def test_the_file_just_written_is_never_evicted(self, tmp_path):
        store = ResultStore(root=str(tmp_path), quota=4)
        result_id, path = store.put("x" * 10)

        assert os.path.exists(path)
        assert store.read(result_id) == "x" * 10

    @pytest.mark.parametrize("kwargs", [{"ttl": 0}, {"ttl": -1}, {"quota": -1}])
    def test_invalid_retention_settings_are_refused(self, kwargs):
        with pytest.raises(ValueError):
            ResultStore(**kwargs)


class TestConcurrentWrites:
    def test_concurrent_writes_get_distinct_ids(self, tmp_path):
        store = ResultStore(root=str(tmp_path))

        def write(index: int) -> tuple[int, str, str]:
            result_id, path = store.put(f"result-{index}")
            return index, result_id, path

        with ThreadPoolExecutor(max_workers=8) as pool:
            written = list(pool.map(write, range(20)))

        assert len({result_id for _, result_id, _ in written}) == 20
        for index, result_id, path in written:
            assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
            assert store.read(result_id) == f"result-{index}"


class TestDefaultStore:
    def test_default_store_is_process_wide(self):
        assert default_result_store() is default_result_store()
