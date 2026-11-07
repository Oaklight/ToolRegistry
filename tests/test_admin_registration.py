"""Tests for source preview/registration and per-tool overrides.

These exercise the admin panel's Register section end to end over HTTP, but
without reaching a real external service: the OpenAPI source is an inline
spec, the Python source is this repository's own ``toolregistry.utils``, and
MCP is covered by its transport validation only.
"""

from __future__ import annotations

import contextlib
import http.server
import json
import threading
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
        self,
        path: str,
        method: str = "GET",
        data: dict | None = None,
        content_type: str | None = "application/json",
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        body = json.dumps(data).encode() if data is not None else None
        headers = dict(extra_headers or {})
        if content_type is not None:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(
            f"{self.info.url}{path}",
            data=body,
            headers=headers,
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


@contextlib.contextmanager
def _serve_spec():
    """Serve ``_SPEC`` as JSON over HTTP on an ephemeral loopback port."""
    payload = json.dumps(_SPEC).encode()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib hook name
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


class TestSpecUrlScheme:
    """A panel-supplied ``spec_url`` may only name an http(s) resource.

    ``load_openapi_spec`` reads a URI with no scheme, or with ``file``, from
    local disk and fetches every other scheme.  Because the panel is
    unauthenticated by default, the scheme is checked in the source layer
    before any I/O starts.  Loopback and private addresses are still allowed:
    blocking them needs a separate decision.
    """

    @pytest.mark.parametrize(
        ("spec_url", "scheme"),
        [
            ("file:///etc/hostname", "file"),
            ("FILE:///etc/hostname", "file"),
            ("data:application/json,%7B%7D", "data"),
            ("ftp://example.com/openapi.json", "ftp"),
            ("/etc/hostname", "(none)"),
        ],
    )
    def test_preview_refuses_a_non_http_spec_url(
        self, server, spec_url: str, scheme: str
    ) -> None:
        status, data = server.request(
            "/api/sources/preview", "POST", {"kind": "openapi", "spec_url": spec_url}
        )

        assert status == 400
        assert scheme in data["message"]
        assert "only http and https" in data["message"]
        assert server.registry.list_tools() == []

    def test_register_refuses_a_non_http_spec_url(self, server) -> None:
        status, data = server.request(
            "/api/sources/register",
            "POST",
            {"kind": "openapi", "spec_url": "file:///etc/hostname"},
        )

        assert status == 400
        assert "only http and https" in data["message"]

    def test_inline_spec_with_a_non_http_spec_url_is_refused(self, server) -> None:
        # Not fetched now, but the URL is stored and a later refresh fetches it.
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            {"kind": "openapi", "spec": _SPEC, "spec_url": "file:///etc/hostname"},
        )

        assert status == 400
        assert "only http and https" in data["message"]

    @pytest.mark.parametrize(
        "spec_url",
        [
            "http://",
            "http://:8080/openapi.json",
            "http://user@/openapi.json",
        ],
    )
    def test_spec_url_needs_a_host(self, server, spec_url: str) -> None:
        status, data = server.request(
            "/api/sources/preview", "POST", {"kind": "openapi", "spec_url": spec_url}
        )

        assert status == 400
        assert "must include a host" in data["message"]

    @pytest.mark.parametrize("scheme", ["http", "HTTP", "Http"])
    def test_preview_fetches_an_http_spec_url(self, server, scheme: str) -> None:
        with _serve_spec() as base_url:
            url = f"{scheme}://{base_url.split('://', 1)[1]}/openapi.json"
            status, data = server.request(
                "/api/sources/preview",
                "POST",
                {
                    "kind": "openapi",
                    "spec_url": url,
                    "base_url": "https://pets.example/api",
                },
            )

        assert status == 200, data
        assert data["info"]["spec_url"] == url
        assert {tool["name"] for tool in data["tools"]} == {
            "list_pets",
            "create_pet",
            "delete_pet",
        }

    @pytest.mark.parametrize(
        "spec_url",
        ["http://example.com/openapi.json", "HTTPS://example.com/openapi.json"],
    )
    def test_http_and_https_are_accepted_in_any_case(self, spec_url: str) -> None:
        from toolregistry.admin.registration import _validate_spec_url

        assert _validate_spec_url(spec_url) == spec_url

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            (
                "HTTP error: 401 for http://user:secret@example.com/openapi.json",
                "HTTP error: 401 for http://example.com/openapi.json",
            ),
            (
                "Network error when fetching URI: "
                "http://user%40name:secret@example.com:8443/spec",
                "Network error when fetching URI: http://example.com:8443/spec",
            ),
        ],
    )
    def test_error_text_drops_credentials(self, text: str, expected: str) -> None:
        from toolregistry.integrations.openapi.utils import redact_url_userinfo

        assert redact_url_userinfo(text) == expected

    def test_fetch_failure_does_not_echo_credentials(self, monkeypatch) -> None:
        import toolregistry.integrations.openapi.utils as openapi_utils
        from toolregistry.admin.registration import SourceError, _load_openapi

        def failing_fetch(url: str) -> dict:
            raise ValueError(f"HTTP error: 401 for {url}")

        monkeypatch.setattr(openapi_utils, "load_openapi_spec", failing_fetch)

        with pytest.raises(SourceError) as excinfo:
            _load_openapi({"spec_url": "http://user:secret@example.com/openapi.json"})

        message = str(excinfo.value)
        assert "secret" not in message
        assert "user:" not in message
        assert "http://example.com/openapi.json" in message


class TestStateChangingGuards:
    """Cross-site and content-type guards on state-changing API calls."""

    @staticmethod
    def _spawn_payload(marker) -> dict:
        """An MCP source that would create *marker* if it were ever started."""
        return {"kind": "mcp", "command": "sh", "args": ["-c", f"touch {marker}"]}

    def test_cross_origin_text_plain_preview_is_refused_without_spawning(
        self, server, tmp_path
    ) -> None:
        marker = tmp_path / "spawned"
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            self._spawn_payload(marker),
            content_type="text/plain",
            extra_headers={"Origin": "https://evil.example"},
        )

        assert status == 403
        assert data["error"] == "Forbidden"
        assert not marker.exists()

    def test_cross_site_fetch_metadata_is_refused(self, server, tmp_path) -> None:
        marker = tmp_path / "spawned"
        status, _ = server.request(
            "/api/sources/preview",
            "POST",
            self._spawn_payload(marker),
            extra_headers={"Sec-Fetch-Site": "cross-site"},
        )

        assert status == 403
        assert not marker.exists()

    def test_state_changing_request_must_be_json(self, server, tmp_path) -> None:
        marker = tmp_path / "spawned"
        status, data = server.request(
            "/api/sources/preview",
            "POST",
            self._spawn_payload(marker),
            content_type="text/plain",
        )

        assert status == 415
        assert "application/json" in data["message"]
        assert not marker.exists()

    def test_reads_are_not_guarded(self, server) -> None:
        status, _ = server.request(
            "/api/tools", extra_headers={"Origin": "https://evil.example"}
        )

        assert status == 200

    def test_same_origin_json_request_passes_the_guard(self, server) -> None:
        status, _ = server.request(
            "/api/sources/preview",
            "POST",
            {"kind": "openapi", "spec": _SPEC},
            extra_headers={"Origin": server.info.url},
        )

        assert status == 200

    def test_stdio_source_is_refused_without_auth_token(self, server, tmp_path) -> None:
        marker = tmp_path / "spawned"
        status, data = server.request(
            "/api/sources/preview", "POST", self._spawn_payload(marker)
        )

        assert status == 403
        assert "auth_token" in data["message"]
        assert not marker.exists()

    def test_transport_spawn_detection(self) -> None:
        from toolregistry.admin.registration import transport_spawns_process

        assert transport_spawns_process({"url": "https://mcp.example/sse"}) is False
        assert transport_spawns_process({"command": "sh"}) is True
        assert transport_spawns_process({"transport": {"command": "sh"}}) is True
        assert transport_spawns_process({"url": "./server.py"}) is True


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

    def test_reregistering_the_source_keeps_the_override(self, server) -> None:
        source = {"kind": "openapi", "spec": _SPEC, "selected": ["list_pets"]}
        status, _ = server.request("/api/sources/register", "POST", source)
        assert status == 200
        original = server.registry.get_tool("list_pets").description

        server.request(
            "/api/tools/list_pets/override", "POST", {"description": "Mine."}
        )

        status, data = server.request("/api/sources/register", "POST", source)

        assert status == 200
        assert data["preserved_overrides"] == ["list_pets"]
        assert server.registry.get_tool("list_pets").description == "Mine."
        assert "list_pets" in server.registry.list_overrides()

        status, _ = server.request("/api/tools/list_pets/override", "DELETE")
        assert status == 200
        assert server.registry.get_tool("list_pets").description == original
        assert server.registry.list_overrides() == {}
