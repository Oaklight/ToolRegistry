"""Tests for source preview/registration and per-tool overrides.

These exercise the admin panel's Register section end to end over HTTP, but
without reaching a real external service: the OpenAPI source is an inline
spec, the Python source is this repository's own ``toolregistry.utils``, and
MCP is covered by its transport validation only.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from toolregistry import ToolRegistry
from toolregistry.admin import AdminServer

_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Pets", "version": "1.0"},
    "servers": [{"url": "https://pets.example/api"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List pets",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}}
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            }
                        }
                    }
                },
            },
        },
        "/pets/{petId}": {
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
            }
        },
    },
}


class _Server:
    """Small context manager around an AdminServer on an ephemeral port."""

    def __init__(self) -> None:
        self.registry = ToolRegistry()
        self.server = AdminServer(self.registry, port=0)
        self.info = self.server.start()
        time.sleep(0.1)

    def __enter__(self) -> _Server:
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.stop()

    def request(
        self, path: str, method: str = "GET", data: dict | None = None
    ) -> tuple[int, dict]:
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(
            f"{self.info.url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")


@pytest.fixture
def server():
    with _Server() as srv:
        yield srv


class TestSourcePreview:
    def test_openapi_preview_lists_tools_without_registering(self, server) -> None:
        status, data = server.request(
            "/api/sources/preview", "POST", {"kind": "openapi", "spec": _SPEC}
        )

        assert status == 200
        assert data["count"] == 3
        # Names follow the registry's separator (``_`` by default).
        names = {tool["name"] for tool in data["tools"]}
        assert names == {"list_pets", "create_pet", "delete_pet"}
        assert data["already_registered"] == 0
        assert all(tool["registered"] is False for tool in data["tools"])
        # Preview must not touch the registry.
        assert server.registry.list_tools() == []

    def test_openapi_preview_applies_the_requested_namespace(self, server) -> None:
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            {"kind": "openapi", "spec": _SPEC, "namespace": "pets"},
        )

        assert status == 200
        names = {tool["name"] for tool in data["tools"]}
        assert names == {"pets-list_pets", "pets-create_pet", "pets-delete_pet"}

    def test_preview_flags_tools_that_are_already_registered(self, server) -> None:
        def list_pets(limit: int = 10) -> list:
            """List pets."""
            return []

        server.registry.register(list_pets, name="list_pets")

        status, data = server.request(
            "/api/sources/preview", "POST", {"kind": "openapi", "spec": _SPEC}
        )

        assert status == 200
        by_name = {tool["name"]: tool for tool in data["tools"]}
        assert by_name["list_pets"]["registered"] is True
        assert by_name["create_pet"]["registered"] is False
        assert data["already_registered"] == 1

    def test_python_preview_reads_a_module(self, server) -> None:
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            {"kind": "python", "module": "toolregistry.utils"},
        )

        assert status == 200
        names = {tool["name"] for tool in data["tools"]}
        assert "normalize_tool_name" in names

    def test_python_preview_reports_an_import_failure(self, server) -> None:
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            {"kind": "python", "module": "no_such_module_anywhere"},
        )

        assert status == 400
        assert "Could not import" in data["message"]

    def test_preview_rejects_an_unknown_kind(self, server) -> None:
        status, data = server.request(
            "/api/sources/preview", "POST", {"kind": "carrier-pigeon"}
        )

        assert status == 400
        assert "Unsupported source kind" in data["message"]

    def test_mcp_preview_requires_a_transport(self, server) -> None:
        status, data = server.request("/api/sources/preview", "POST", {"kind": "mcp"})

        assert status == 400
        assert "MCP 'url'" in data["message"]


class TestSourceRegistration:
    def test_registering_a_selection_keeps_only_what_was_picked(self, server) -> None:
        status, data = server.request(
            "/api/sources/register",
            "POST",
            {
                "kind": "openapi",
                "spec": _SPEC,
                "selected": ["list_pets"],
            },
        )

        assert status == 200
        assert data["count"] == 1
        assert server.registry.list_tools() == ["list_pets"]

    def test_registering_without_a_selection_keeps_everything(self, server) -> None:
        status, data = server.request(
            "/api/sources/register", "POST", {"kind": "openapi", "spec": _SPEC}
        )

        assert status == 200
        assert sorted(data["registered"]) == ["create_pet", "delete_pet", "list_pets"]
        assert sorted(server.registry.list_tools(include_disabled=True)) == [
            "create_pet",
            "delete_pet",
            "list_pets",
        ]

    def test_registration_applies_the_namespace(self, server) -> None:
        status, data = server.request(
            "/api/sources/register",
            "POST",
            {
                "kind": "openapi",
                "spec": _SPEC,
                "namespace": "pets",
                "selected": ["pets-list_pets"],
            },
        )

        assert status == 200
        assert data["registered"] == ["pets-list_pets"]
        assert server.registry.get_tool("pets-list_pets").namespace == "pets"

    def test_registering_python_functions(self, server) -> None:
        status, data = server.request(
            "/api/sources/register",
            "POST",
            {
                "kind": "python",
                "module": "toolregistry.utils",
                "selected": ["normalize_tool_name"],
            },
        )

        assert status == 200
        assert data["registered"] == ["normalize_tool_name"]
        assert server.registry.list_tools() == ["normalize_tool_name"]

    def test_registering_an_empty_selection_is_rejected(self, server) -> None:
        status, data = server.request(
            "/api/sources/register",
            "POST",
            {"kind": "python", "module": "toolregistry.utils", "selected": ["nope"]},
        )

        assert status == 400
        assert server.registry.list_tools() == []

    def test_register_rejects_a_malformed_selection(self, server) -> None:
        status, data = server.request(
            "/api/sources/register",
            "POST",
            {"kind": "openapi", "spec": _SPEC, "selected": "list_pets"},
        )

        assert status == 400
        assert "'selected' must be a list" in data["message"]


class TestRequestHeaders:
    """Auth is flattened by the panel, so the mapping is worth pinning."""

    def test_bearer_token_becomes_an_authorization_header(self) -> None:
        from toolregistry.admin.registration import _request_headers

        headers = _request_headers({"auth": {"type": "bearer", "token": "abc"}})
        assert headers == {"Authorization": "Bearer abc"}

    def test_basic_auth_is_base64_encoded(self) -> None:
        from toolregistry.admin.registration import _request_headers

        headers = _request_headers(
            {"auth": {"type": "basic", "username": "u", "password": "p"}}
        )
        assert headers == {"Authorization": "Basic dTpw"}

    def test_explicit_authorization_header_wins(self) -> None:
        from toolregistry.admin.registration import _request_headers

        headers = _request_headers(
            {
                "headers": {"Authorization": "Token xyz"},
                "auth": {"type": "bearer", "token": "abc"},
            }
        )
        assert headers == {"Authorization": "Token xyz"}

    def test_extra_headers_are_kept_alongside_auth(self) -> None:
        from toolregistry.admin.registration import _request_headers

        headers = _request_headers(
            {
                "headers": {"X-Trace": "panel"},
                "auth": {"type": "bearer", "token": "abc"},
            }
        )
        assert headers == {"X-Trace": "panel", "Authorization": "Bearer abc"}

    def test_no_headers_means_none(self) -> None:
        from toolregistry.admin.registration import _request_headers

        assert _request_headers({}) is None
        assert _request_headers({"auth": {"type": "none"}}) is None

    def test_bearer_without_a_token_is_rejected(self) -> None:
        from toolregistry.admin.registration import SourceError, _request_headers

        with pytest.raises(SourceError, match="needs a 'token'"):
            _request_headers({"auth": {"type": "bearer"}})


class TestProviderSafeNames:
    def test_slashes_and_overlong_names_are_reported(self) -> None:
        from toolregistry.admin.registration import invalid_tool_names

        bad = invalid_tool_names(["ok_name", "fs/read", "x" * 65, "dotted.name"])
        assert bad == ["dotted.name", "fs/read", "x" * 65]

    def test_preview_reports_invalid_names_for_openapi(self, server) -> None:
        spec = {
            "openapi": "3.0.0",
            "servers": [{"url": "https://api.example"}],
            "paths": {"/a": {"get": {"operationId": "listItems"}}},
        }
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            {"kind": "openapi", "spec": spec, "namespace": "fs/x"},
        )

        assert status == 200
        assert data["invalid_names"], data
        assert all("/" in name for name in data["invalid_names"])


class TestToolOverrides:
    def _register(self, server: _Server) -> None:
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        server.registry.register(add, namespace="math")

    def test_override_changes_description_and_is_listed(self, server) -> None:
        self._register(server)

        status, data = server.request(
            "/api/tools/math-add/override",
            "POST",
            {"description": "Sum two integers.", "custom_tags": ["core"]},
        )

        assert status == 200
        assert data["current"]["description"] == "Sum two integers."
        assert server.registry.get_tool("math-add").description == "Sum two integers."

        status, listing = server.request("/api/overrides")
        assert status == 200
        assert listing["count"] == 1
        entry = listing["overrides"][0]
        assert entry["name"] == "math-add"
        assert entry["original"]["description"] == "Add two numbers."
        assert entry["current"]["description"] == "Sum two integers."

    def test_override_keeps_the_tool_callable(self, server) -> None:
        self._register(server)
        server.request("/api/tools/math-add/override", "POST", {"description": "Sum."})

        result = server.registry.execute_tool_calls(
            [
                {
                    "id": "1",
                    "function": {"name": "math-add", "arguments": '{"a": 2, "b": 3}'},
                }
            ]
        )
        assert str(result[0].result) == "5"

    def test_restore_drops_the_override(self, server) -> None:
        self._register(server)
        server.request("/api/tools/math-add/override", "POST", {"description": "Sum."})

        status, data = server.request("/api/tools/math-add/override", "DELETE")

        assert status == 200
        assert server.registry.get_tool("math-add").description == "Add two numbers."
        assert server.registry.list_overrides() == {}

    def test_restore_without_an_override_is_a_404(self, server) -> None:
        self._register(server)

        status, _ = server.request("/api/tools/math-add/override", "DELETE")

        assert status == 404

    def test_override_rejects_unknown_fields_without_partial_application(
        self, server
    ) -> None:
        self._register(server)

        status, data = server.request(
            "/api/tools/math-add/override",
            "POST",
            {"description": "Sum.", "colour": "red"},
        )

        assert status == 400
        assert "colour" in data["message"]
        assert server.registry.get_tool("math-add").description == "Add two numbers."
        assert server.registry.list_overrides() == {}

    def test_override_validates_tag_names(self, server) -> None:
        self._register(server)

        status, data = server.request(
            "/api/tools/math-add/override", "POST", {"tags": ["not-a-real-tag"]}
        )

        assert status == 400
        assert "Unknown tag" in data["message"]

    def test_override_404s_for_an_unknown_tool(self, server) -> None:
        status, _ = server.request(
            "/api/tools/ghost/override", "POST", {"description": "x"}
        )

        assert status == 404
