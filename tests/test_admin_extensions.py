"""Tests for the admin panel extension contract.

The contract has three server-side surfaces: the manifest at
``GET /api/extensions``, extension routes under ``/ext/<name>``, and
extension assets under ``assets/ext/<name>/``.  These tests exercise each
surface through a running server, plus the validation that refuses to start
on a bad contract.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from toolregistry import (
    ADMIN_EXTENSION_API,
    AdminExtensionError,
    AdminServer,
    ToolRegistry,
)
from toolregistry.admin.extensions import prepare_extensions
from toolregistry.admin.static import read_shell


class ClockExtension:
    """A minimal extension with one GET, one path route and one POST."""

    name = "clock"
    title = {"en": "Clock", "zh": "时钟"}
    entry = "assets/ext/clock/main.js"
    requires_api = ADMIN_EXTENSION_API
    styles = ("assets/ext/clock/style.css",)
    icon = "<svg viewBox='0 0 24 24'><circle cx='12' cy='12' r='9'></circle></svg>"
    nav = {"order": 10}

    def __init__(self, assets: Path) -> None:
        self.assets = assets
        self.registered = False
        self.context = None

    def register(self, ctx) -> None:
        self.registered = True
        self.context = ctx
        ctx.get("/now", self.now)
        ctx.get("/echo/<path:value>", self.echo)
        ctx.post("/poke", self.poke)

    def now(self, request):
        return {"now": "tick"}

    def echo(self, request, value):
        return {"value": value}

    def poke(self, request):
        return {"poked": True}


@pytest.fixture()
def assets_dir(tmp_path: Path) -> Path:
    """Create an extension asset directory with a module and a stylesheet."""
    root = tmp_path / "clock"
    (root / "lib").mkdir(parents=True)
    (root / "main.js").write_text(
        "export function register({container}) { container.textContent = 'ok'; }\n",
        encoding="utf-8",
    )
    (root / "lib" / "helper.js").write_text("export const x = 1;\n", encoding="utf-8")
    (root / "style.css").write_text(".clock { color: red; }\n", encoding="utf-8")
    return root


def _request(
    url: str,
    method: str = "GET",
    data: dict | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, str]:
    """Make an HTTP request and return status, body and content type."""
    all_headers = {"Content-Type": "application/json"}
    if token:
        all_headers["Authorization"] = f"Bearer {token}"
    if headers:
        all_headers.update(headers)

    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return (
                response.status,
                response.read(),
                response.headers.get("Content-Type", ""),
            )
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get("Content-Type", "")


class TestExtensionsMounted:
    """A running server with one extension mounted."""

    @pytest.fixture()
    def server(self, assets_dir: Path):
        extension = ClockExtension(assets_dir)
        admin = AdminServer(ToolRegistry(), port=0, extensions=[extension])
        info = admin.start()
        try:
            yield admin, info, extension
        finally:
            admin.stop()

    def test_manifest_describes_extension(self, server) -> None:
        _, info, _ = server
        status, body, _ = _request(f"{info.url}/api/extensions")

        assert status == 200
        payload = json.loads(body)
        assert payload["api_version"] == ADMIN_EXTENSION_API
        assert len(payload["extensions"]) == 1
        manifest = payload["extensions"][0]
        assert manifest["name"] == "clock"
        assert manifest["title"] == {"en": "Clock", "zh": "时钟"}
        assert manifest["entry"] == "assets/ext/clock/main.js"
        assert manifest["styles"] == ["assets/ext/clock/style.css"]
        assert manifest["api_prefix"] == "/ext/clock"
        assert manifest["requires_api"] == ADMIN_EXTENSION_API
        assert manifest["nav"] == {"group": None, "order": 10}
        assert manifest["icon"].startswith("<svg")

    def test_registration_ran_before_serving(self, server) -> None:
        _, _, extension = server
        assert extension.registered is True
        assert extension.context.api_prefix == "/ext/clock"

    def test_extension_route(self, server) -> None:
        _, info, _ = server
        status, body, _ = _request(f"{info.url}/ext/clock/now")

        assert status == 200
        assert json.loads(body) == {"now": "tick"}

    def test_extension_path_route(self, server) -> None:
        _, info, _ = server
        status, body, _ = _request(f"{info.url}/ext/clock/echo/a/b")

        assert status == 200
        assert json.loads(body) == {"value": "a/b"}

    def test_cross_origin_post_to_extension_is_refused(self, server) -> None:
        _, info, _ = server
        status, body, _ = _request(
            f"{info.url}/ext/clock/poke",
            method="POST",
            data={},
            headers={"Origin": "https://evil.example"},
        )

        assert status == 403
        assert b"Cross-origin" in body

    def test_extension_post_requires_json(self, server) -> None:
        _, info, _ = server
        request = urllib.request.Request(
            f"{info.url}/ext/clock/poke",
            data=b"x=1",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(request, timeout=5)

        assert excinfo.value.code == 415

    def test_same_origin_post_succeeds(self, server) -> None:
        _, info, _ = server
        status, body, _ = _request(f"{info.url}/ext/clock/poke", method="POST", data={})

        assert status == 200
        assert json.loads(body) == {"poked": True}

    def test_extension_asset_is_served(self, server) -> None:
        _, info, _ = server
        status, body, content_type = _request(f"{info.url}/assets/ext/clock/main.js")

        assert status == 200
        assert content_type.startswith("application/javascript")
        assert b"export function register" in body

    def test_nested_extension_asset_is_served(self, server) -> None:
        _, info, _ = server
        status, body, _ = _request(f"{info.url}/assets/ext/clock/lib/helper.js")

        assert status == 200
        assert b"export const x = 1" in body

    def test_extension_stylesheet_is_served(self, server) -> None:
        _, info, _ = server
        status, _, content_type = _request(f"{info.url}/assets/ext/clock/style.css")

        assert status == 200
        assert content_type.startswith("text/css")

    def test_unknown_extension_asset_is_404(self, server) -> None:
        _, info, _ = server
        status, _, _ = _request(f"{info.url}/assets/ext/other/main.js")

        assert status == 404

    def test_asset_traversal_is_refused(self, server) -> None:
        _, info, _ = server
        status, _, _ = _request(f"{info.url}/assets/ext/clock/../secret.js")

        assert status == 404

    def test_symlink_escape_is_refused(self, server, tmp_path: Path) -> None:
        _, info, extension = server
        secret = tmp_path / "secret.js"
        secret.write_text("const secret = 1;\n", encoding="utf-8")
        (extension.assets / "link.js").symlink_to(secret)

        status, _, _ = _request(f"{info.url}/assets/ext/clock/link.js")

        assert status == 404

    def test_unknown_extension_route_is_404(self, server) -> None:
        _, info, _ = server
        status, _, _ = _request(f"{info.url}/ext/clock/missing")

        assert status == 404


class ApiOnlyExtension:
    """An extension with routes but no tab and no assets."""

    name = "api-only"
    title = {"en": "API only"}
    requires_api = ADMIN_EXTENSION_API

    def register(self, ctx) -> None:
        ctx.get("/ping", self.ping)

    def ping(self, request):
        return {"pong": True}


class TestApiOnlyExtension:
    """An extension may omit nav, assets, entry and styles."""

    @pytest.fixture()
    def server(self):
        admin = AdminServer(ToolRegistry(), port=0, extensions=[ApiOnlyExtension()])
        info = admin.start()
        try:
            yield info
        finally:
            admin.stop()

    def test_manifest_has_no_nav_or_entry(self, server) -> None:
        status, body, _ = _request(f"{server.url}/api/extensions")

        assert status == 200
        manifest = json.loads(body)["extensions"][0]
        assert manifest["name"] == "api-only"
        assert manifest["nav"] is None
        assert manifest["entry"] is None
        assert manifest["styles"] == []

    def test_routes_are_mounted(self, server) -> None:
        status, body, _ = _request(f"{server.url}/ext/api-only/ping")

        assert status == 200
        assert json.loads(body) == {"pong": True}

    def test_no_assets_are_served(self, server) -> None:
        status, _, _ = _request(f"{server.url}/assets/ext/api-only/main.js")

        assert status == 404


class TestExtensionAuthentication:
    """Extension routes and assets inherit the panel's auth policy."""

    @pytest.fixture()
    def server(self, assets_dir: Path):
        extension = ClockExtension(assets_dir)
        admin = AdminServer(
            ToolRegistry(),
            port=0,
            auth_token="extension-token",
            extensions=[extension],
        )
        info = admin.start()
        try:
            yield info
        finally:
            admin.stop()

    def test_manifest_requires_token(self, server) -> None:
        status, _, _ = _request(f"{server.url}/api/extensions")
        assert status == 401

        status, body, _ = _request(
            f"{server.url}/api/extensions", token="extension-token"
        )
        assert status == 200
        assert json.loads(body)["extensions"][0]["name"] == "clock"

    def test_extension_route_requires_token(self, server) -> None:
        status, _, _ = _request(f"{server.url}/ext/clock/now")
        assert status == 401

        status, body, _ = _request(
            f"{server.url}/ext/clock/now", token="extension-token"
        )
        assert status == 200
        assert json.loads(body) == {"now": "tick"}

    def test_asset_stays_public_with_ui(self, server) -> None:
        # The shell must load its scripts before the token prompt can run, so
        # extension assets follow the same rule as the panel's own assets.
        status, _, _ = _request(f"{server.url}/assets/ext/clock/main.js")
        assert status == 200


class TestExtensionValidation:
    """Contract violations are refused at prepare time."""

    def _prepare(self, extension: object) -> None:
        prepare_extensions([extension])

    def test_api_mismatch_names_extension(self, assets_dir: Path) -> None:
        class Future(ClockExtension):
            requires_api = ADMIN_EXTENSION_API + 1

        with pytest.raises(AdminExtensionError, match="clock"):
            self._prepare(Future(assets_dir))

    def test_invalid_name_is_refused(self, assets_dir: Path) -> None:
        class BadName(ClockExtension):
            name = "../clock"

        with pytest.raises(AdminExtensionError, match="name"):
            self._prepare(BadName(assets_dir))

    def test_duplicate_name_is_refused(self, assets_dir: Path) -> None:
        with pytest.raises(AdminExtensionError, match="duplicate"):
            prepare_extensions([ClockExtension(assets_dir), ClockExtension(assets_dir)])

    def test_entry_outside_prefix_is_refused(self, assets_dir: Path) -> None:
        class WrongEntry(ClockExtension):
            entry = "assets/ext/other/main.js"

        with pytest.raises(AdminExtensionError, match="clock"):
            self._prepare(WrongEntry(assets_dir))

    def test_unsupported_asset_type_is_refused(self, assets_dir: Path) -> None:
        class HtmlEntry(ClockExtension):
            entry = "assets/ext/clock/page.html"

        with pytest.raises(AdminExtensionError, match="unsupported"):
            self._prepare(HtmlEntry(assets_dir))

    def test_missing_asset_is_refused(self, assets_dir: Path) -> None:
        class MissingEntry(ClockExtension):
            entry = "assets/ext/clock/absent.js"

        with pytest.raises(AdminExtensionError, match="absent.js"):
            self._prepare(MissingEntry(assets_dir))

    def test_missing_assets_directory_is_refused(self) -> None:
        class NoAssets(ClockExtension):
            def __init__(self) -> None:
                self.assets = None

        with pytest.raises(AdminExtensionError, match="assets directory"):
            self._prepare(NoAssets())

    def test_nav_without_entry_is_refused(self, assets_dir: Path) -> None:
        class NavNoEntry(ClockExtension):
            entry = None

        with pytest.raises(AdminExtensionError, match="no entry module"):
            self._prepare(NavNoEntry(assets_dir))

    def test_nav_group_must_be_a_key(self, assets_dir: Path) -> None:
        class LabelGroup(ClockExtension):
            nav = {"group": "Utilities"}

        with pytest.raises(AdminExtensionError, match="lower-case key"):
            self._prepare(LabelGroup(assets_dir))

    def test_unknown_nav_key_is_refused(self, assets_dir: Path) -> None:
        class BadNav(ClockExtension):
            nav = {"order": 1, "colour": "red"}

        with pytest.raises(AdminExtensionError, match="unknown keys"):
            self._prepare(BadNav(assets_dir))

    def test_register_failure_names_extension(self, assets_dir: Path) -> None:
        class Exploding(ClockExtension):
            def register(self, ctx) -> None:
                raise ValueError("boom")

        admin = AdminServer(ToolRegistry(), port=0, extensions=[Exploding(assets_dir)])
        with pytest.raises(AdminExtensionError, match="clock"):
            admin.start()

        # A failed start leaves no half-mounted app behind.
        assert admin.is_running() is False
        assert admin._app is None

    def test_bad_route_path_is_refused(self, assets_dir: Path) -> None:
        class BadRoute(ClockExtension):
            def register(self, ctx) -> None:
                ctx.get("../elsewhere", self.now)

        admin = AdminServer(ToolRegistry(), port=0, extensions=[BadRoute(assets_dir)])
        with pytest.raises(AdminExtensionError, match="clock"):
            admin.start()

    def test_duplicate_route_is_refused(self, assets_dir: Path) -> None:
        class DoubleRoute(ClockExtension):
            def register(self, ctx) -> None:
                ctx.get("/now", self.now)
                ctx.get("/now", self.now)

        admin = AdminServer(
            ToolRegistry(), port=0, extensions=[DoubleRoute(assets_dir)]
        )
        with pytest.raises(AdminExtensionError, match="already registered"):
            admin.start()


class TestNoExtensions:
    """A panel without extensions advertises an empty list."""

    def test_manifest_is_empty(self) -> None:
        admin = AdminServer(ToolRegistry(), port=0)
        info = admin.start()
        try:
            status, body, _ = _request(f"{info.url}/api/extensions")
        finally:
            admin.stop()

        assert status == 200
        assert json.loads(body) == {
            "api_version": ADMIN_EXTENSION_API,
            "extensions": [],
        }


class TestShellWiring:
    """The shell loads the extension loader before init runs."""

    def test_shell_includes_loader(self) -> None:
        shell = read_shell()

        assert "assets/js/core/extensions.js" in shell
        assert shell.index("core/extensions.js") < shell.index("core/init.js")


def test_extension_names_are_regex_checked(assets_dir: Path) -> None:
    """A name with an uppercase letter is not a valid URL segment."""

    class Upper(ClockExtension):
        name = "Clock"

    with pytest.raises(AdminExtensionError, match="must match"):
        prepare_extensions([Upper(assets_dir)])
