"""Tests for the admin source persistence and status hook.

The hook has three server-side effects: a registration is handed to
``persist`` as a structured change, a persistence failure is reported without
claiming the registration failed, and ``GET /api/sources`` carries the hook's
records verbatim alongside the unchanged tool-derived list.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

import pytest

from toolregistry import (
    AdminInfo,
    AdminServer,
    SourceChange,
    SourcePersistenceError,
    SourcePersistenceHook,
    ToolRegistry,
)

TOKEN = "hook-token"
REGISTER = "/api/sources/register"


def _request(
    url: str,
    method: str = "GET",
    data: dict | None = None,
    token: str | None = TOKEN,
) -> tuple[int, dict]:
    """Make a JSON request and return the status and decoded body."""
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


class RecordingHook:
    """A hook that records changes and returns a fixed record shape."""

    def __init__(self, records: list[dict] | None = None) -> None:
        self.changes: list[SourceChange] = []
        self.records: list[dict] = list(records or [])
        self.error: BaseException | None = None
        self.status_error: BaseException | None = None
        self.writable_error: BaseException | None = None
        self.writable_value = True
        self.return_missing = False

    def persist(self, change: SourceChange) -> Mapping[str, Any]:
        self.changes.append(change)
        if self.error is not None:
            raise self.error
        if self.return_missing:
            return None  # type: ignore
        record = {
            "id": "src_0123456789abcdef",
            "kind": change.kind,
            "detail": "calendar",
            "namespace": change.namespace,
            "status": "applied",
            "last_error": None,
            "names": list(change.selected or ()),
        }
        self.records.append(record)
        return record

    def writable(self) -> bool:
        if self.writable_error is not None:
            raise self.writable_error
        return self.writable_value

    def statuses(self) -> list[dict]:
        if self.status_error is not None:
            raise self.status_error
        return list(self.records)


def _start(hook: RecordingHook | None) -> tuple[AdminServer, AdminInfo]:
    admin = AdminServer(ToolRegistry(), port=0, auth_token=TOKEN, source_hook=hook)
    return admin, admin.start()


@pytest.fixture()
def server():
    hook = RecordingHook()
    admin, info = _start(hook)
    try:
        yield info, hook
    finally:
        admin.stop()


def _register_python(url: str) -> tuple[int, dict]:
    return _request(
        f"{url}{REGISTER}",
        method="POST",
        data={"kind": "python", "module": "calendar", "selected": ["isleap"]},
    )


class TestPersistence:
    """Registration hands a structured change to the hook."""

    def test_change_is_structured(self, server) -> None:
        info, hook = server

        status, body = _register_python(info.url)

        assert status == 200
        assert body["persisted"] is True
        assert body["source"]["id"] == "src_0123456789abcdef"
        assert len(hook.changes) == 1
        change = hook.changes[0]
        assert change.action == "add"
        assert change.kind == "python"
        assert change.payload["module"] == "calendar"
        assert change.payload["selected"] == ["isleap"]
        assert change.namespace is None
        assert change.selected == ("isleap",)

    def test_registered_tool_is_live(self, server) -> None:
        info, _ = server
        _register_python(info.url)

        status, body = _request(f"{info.url}/api/tools/isleap")

        assert status == 200
        assert body["name"] == "isleap"

    def test_persist_failure_keeps_the_registration(self, server) -> None:
        info, hook = server
        hook.error = SourcePersistenceError("configuration is read-only")

        status, body = _register_python(info.url)

        # The tools are live, so the response reports the persistence failure
        # without claiming the registration failed.
        assert status == 200
        assert body["persisted"] is False
        assert body["persist_error"] == "configuration is read-only"
        assert body["registered"] == ["isleap"]

        status, _ = _request(f"{info.url}/api/tools/isleap")
        assert status == 200

    def test_unexpected_hook_error_is_reported(self, server) -> None:
        info, hook = server
        hook.error = RuntimeError("boom")

        status, body = _register_python(info.url)

        assert status == 200
        assert body["persisted"] is False
        assert body["persist_error"] == "boom"

    def test_missing_record_is_a_persist_failure(self, server) -> None:
        info, hook = server
        hook.return_missing = True

        status, body = _register_python(info.url)

        assert status == 200
        assert body["persisted"] is False
        assert "no source record" in body["persist_error"]

    def test_no_hook_leaves_the_registration_response_unchanged(self) -> None:
        admin, info = _start(None)
        try:
            status, body = _register_python(info.url)
        finally:
            admin.stop()

        assert status == 200
        assert "persisted" not in body
        assert "source" not in body
        assert body["registered"] == ["isleap"]


class TestListing:
    """``GET /api/sources`` exposes status without changing its old shape."""

    def test_records_are_passed_through(self, server) -> None:
        info, hook = server
        failed = {
            "id": "src_fedcba9876543210",
            "kind": "mcp",
            "detail": "python ...",
            "namespace": None,
            "status": "failed",
            "last_error": "connection refused",
            "names": [],
        }
        _register_python(info.url)
        hook.records.append(failed)

        status, body = _request(f"{info.url}/api/sources")

        assert status == 200
        assert body["config_writable"] is True
        assert body["source_status"][-1] == failed
        assert len(body["source_status"]) == 2
        # The tool-derived entry keeps exactly its old keys.
        entry = body["sources"][0]
        assert set(entry) == {
            "type",
            "detail",
            "namespace",
            "tool_count",
            "enabled_count",
            "tools",
        }
        assert entry["tools"] == ["isleap"]

    def test_status_failure_keeps_the_listing(self, server) -> None:
        info, hook = server
        _register_python(info.url)
        hook.status_error = RuntimeError("status backend down")

        status, body = _request(f"{info.url}/api/sources")

        assert status == 200
        assert body["source_status"] == []
        assert body["sources"][0]["tools"] == ["isleap"]

    def test_unserialisable_record_is_skipped(self, server) -> None:
        info, hook = server
        good = {
            "id": "src_good",
            "kind": "python",
            "detail": "calendar",
            "namespace": None,
            "status": "applied",
            "last_error": None,
            "names": [],
        }
        hook.records = [good, {**good, "id": "src_bad", "detail": object()}]

        status, body = _request(f"{info.url}/api/sources")

        assert status == 200
        assert [record["id"] for record in body["source_status"]] == ["src_good"]

    def test_writable_failure_is_reported_as_false(self, server) -> None:
        info, hook = server
        hook.writable_error = RuntimeError("cannot stat")

        status, body = _request(f"{info.url}/api/sources")

        assert status == 200
        assert body["config_writable"] is False

    def test_without_hook_the_response_is_unchanged(self) -> None:
        admin, info = _start(None)
        try:
            _register_python(info.url)
            status, body = _request(f"{info.url}/api/sources")
        finally:
            admin.stop()

        assert status == 200
        assert set(body) == {"sources"}
        assert set(body["sources"][0]) == {
            "type",
            "detail",
            "namespace",
            "tool_count",
            "enabled_count",
            "tools",
        }


class TestHookContract:
    """The change and protocol shapes are explicit."""

    def test_invalid_action_is_refused(self) -> None:
        with pytest.raises(ValueError, match="action must be one of"):
            SourceChange(
                action="upsert",
                kind="python",
                payload={},
                namespace=None,
            )

    def test_hook_matches_the_protocol(self) -> None:
        assert isinstance(RecordingHook(), SourcePersistenceHook)

    def test_repr_hides_the_payload(self) -> None:
        change = SourceChange(
            action="add",
            kind="mcp",
            payload={"headers": {"Authorization": "Bearer SECRET-TOKEN"}},
            namespace=None,
        )

        assert "SourceChange" in repr(change)
        assert "SECRET-TOKEN" not in repr(change)
