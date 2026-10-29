"""Tests for admin panel server functionality.

This module tests the AdminServer, TokenAuth, and REST API endpoints.
"""

import asyncio
import json
import shutil
import ssl
import subprocess
import time
import urllib.request
import urllib.error
from types import SimpleNamespace

import pytest

from toolregistry import (
    AdminInfo,
    AdminServer,
    RequestMetrics,
    TokenAuth,
    ToolRegistry,
)
from toolregistry.permissions import PermissionPolicy, PermissionResult, PermissionRule
from toolregistry.tool import ToolTag


class TestTokenAuth:
    """Tests for TokenAuth class."""

    def test_init_with_token(self) -> None:
        """Test initialization with provided token."""
        auth = TokenAuth("my_secret_token")
        assert auth.token == "my_secret_token"

    def test_init_without_token(self) -> None:
        """Test initialization generates random token."""
        auth = TokenAuth()
        assert len(auth.token) == 32  # 16 bytes = 32 hex chars
        assert auth.token.isalnum()

    def test_verify_correct_token(self) -> None:
        """Test verification with correct token."""
        auth = TokenAuth("test_token")
        assert auth.verify("test_token") is True

    def test_verify_incorrect_token(self) -> None:
        """Test verification with incorrect token."""
        auth = TokenAuth("test_token")
        assert auth.verify("wrong_token") is False

    def test_verify_empty_token(self) -> None:
        """Test verification with empty token."""
        auth = TokenAuth("test_token")
        assert auth.verify("") is False

    def test_different_instances_different_tokens(self) -> None:
        """Test that different instances generate different tokens."""
        auth1 = TokenAuth()
        auth2 = TokenAuth()
        assert auth1.token != auth2.token


class TestAdminServer:
    """Tests for AdminServer class."""

    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        registry = ToolRegistry()
        server = AdminServer(registry)
        assert server.host == "127.0.0.1"
        assert server.port == 8081
        assert server.serve_ui is True
        assert server.auth is None

    def test_init_remote_generates_token(self) -> None:
        """Test that remote mode generates auth token."""
        registry = ToolRegistry()
        server = AdminServer(registry, remote=True)
        assert server.host == "0.0.0.0"
        assert server.auth is not None
        assert len(server.auth.token) == 32

    def test_init_with_custom_token(self) -> None:
        """Test initialization with custom auth token."""
        registry = ToolRegistry()
        server = AdminServer(registry, auth_token="custom_token")
        assert server.auth is not None
        assert server.auth.token == "custom_token"

    def test_start_and_stop(self) -> None:
        """Test server start and stop."""
        registry = ToolRegistry()
        server = AdminServer(registry, port=18081)

        # Start server
        info = server.start()
        assert server.is_running()
        assert isinstance(info, AdminInfo)
        assert info.port == 18081
        assert "http://" in info.url

        # Stop server
        server.stop()
        assert not server.is_running()

    def test_start_already_running(self) -> None:
        """Test that starting an already running server raises error."""
        registry = ToolRegistry()
        server = AdminServer(registry, port=18082)

        try:
            server.start()
            with pytest.raises(RuntimeError, match="already running"):
                server.start()
        finally:
            server.stop()

    def test_find_available_port(self) -> None:
        """Test finding available port."""
        port = AdminServer.find_available_port("127.0.0.1", 18090)
        assert port >= 18090
        assert port < 18190

    def test_get_info_when_running(self) -> None:
        """Test get_info returns info when server is running."""
        registry = ToolRegistry()
        server = AdminServer(registry, port=18083)

        try:
            server.start()
            info = server.get_info()
            assert info is not None
            assert info.port == 18083
        finally:
            server.stop()

    def test_get_info_when_not_running(self) -> None:
        """Test get_info returns None when server is not running."""
        registry = ToolRegistry()
        server = AdminServer(registry)
        assert server.get_info() is None


class TestAdminServerAPI:
    """Tests for REST API endpoints."""

    @pytest.fixture
    def server_with_tools(self):
        """Create a server with some registered tools."""
        registry = ToolRegistry()

        # Register some test tools
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        def subtract(a: int, b: int) -> int:
            """Subtract two numbers."""
            return a - b

        registry.register(add, namespace="math")
        registry.register(subtract, namespace="math")

        server = AdminServer(registry, port=18084)
        info = server.start()
        time.sleep(0.1)  # Give server time to start

        yield server, info

        server.stop()

    def _request(
        self,
        url: str,
        method: str = "GET",
        data: dict | None = None,
        token: str | None = None,
    ) -> tuple[int, dict]:
        """Make HTTP request and return status code and JSON response."""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_get_tools(self, server_with_tools) -> None:
        """Test GET /api/tools endpoint."""
        server, info = server_with_tools
        status, data = self._request(f"{info.url}/api/tools")

        assert status == 200
        assert "tools" in data
        assert len(data["tools"]) == 2

    def test_get_single_tool(self, server_with_tools) -> None:
        """Test GET /api/tools/{name} endpoint."""
        server, info = server_with_tools
        # Tool names are normalized to use hyphens (math-add instead of math.add)
        status, data = self._request(f"{info.url}/api/tools/math-add")

        assert status == 200
        assert data["name"] == "math-add"
        assert data["enabled"] is True
        assert "schema" in data

    def test_get_nonexistent_tool(self, server_with_tools) -> None:
        """Test GET /api/tools/{name} for nonexistent tool."""
        server, info = server_with_tools
        status, data = self._request(f"{info.url}/api/tools/nonexistent")

        assert status == 404
        assert "error" in data

    def test_disable_and_enable_tool(self, server_with_tools) -> None:
        """Test POST /api/tools/{name}/disable and enable endpoints."""
        server, info = server_with_tools
        # Tool names are normalized to use hyphens
        tool_name = "math-add"

        # Disable tool
        status, data = self._request(
            f"{info.url}/api/tools/{tool_name}/disable",
            method="POST",
            data={"reason": "Testing"},
        )
        assert status == 200
        assert data["success"] is True

        # Verify disabled
        status, data = self._request(f"{info.url}/api/tools/{tool_name}")
        assert data["enabled"] is False
        assert data["reason"] == "Testing"

        # Enable tool
        status, data = self._request(
            f"{info.url}/api/tools/{tool_name}/enable",
            method="POST",
        )
        assert status == 200
        assert data["success"] is True

        # Verify enabled
        status, data = self._request(f"{info.url}/api/tools/{tool_name}")
        assert data["enabled"] is True

    def test_get_namespaces(self, server_with_tools) -> None:
        """Test GET /api/namespaces endpoint."""
        server, info = server_with_tools
        status, data = self._request(f"{info.url}/api/namespaces")

        assert status == 200
        assert "namespaces" in data
        assert len(data["namespaces"]) == 1
        assert data["namespaces"][0]["name"] == "math"
        assert data["namespaces"][0]["tool_count"] == 2

    def test_disable_namespace(self, server_with_tools) -> None:
        """Test POST /api/namespaces/{ns}/disable endpoint."""
        server, info = server_with_tools
        # Tool names are normalized to use hyphens
        tool_name = "math-add"

        status, data = self._request(
            f"{info.url}/api/namespaces/math/disable",
            method="POST",
            data={"reason": "Maintenance"},
        )
        assert status == 200
        assert data["success"] is True
        assert data["tools_affected"] == 2

        # Verify tools are disabled
        status, data = self._request(f"{info.url}/api/tools/{tool_name}")
        assert data["enabled"] is False

    def test_enable_namespace(self, server_with_tools) -> None:
        """Test POST /api/namespaces/{ns}/enable endpoint."""
        server, info = server_with_tools
        # Tool names are normalized to use hyphens
        tool_name = "math-add"

        # First disable
        self._request(
            f"{info.url}/api/namespaces/math/disable",
            method="POST",
        )

        # Then enable
        status, data = self._request(
            f"{info.url}/api/namespaces/math/enable",
            method="POST",
        )
        assert status == 200
        assert data["success"] is True

        # Verify tools are enabled
        status, data = self._request(f"{info.url}/api/tools/{tool_name}")
        assert data["enabled"] is True

    def test_export_state(self, server_with_tools) -> None:
        """Test GET /api/state endpoint."""
        server, info = server_with_tools
        # Tool names are normalized to use hyphens
        tool_name = "math-add"

        # Disable a tool first
        self._request(
            f"{info.url}/api/tools/{tool_name}/disable",
            method="POST",
            data={"reason": "Test"},
        )

        status, data = self._request(f"{info.url}/api/state")
        assert status == 200
        assert "disabled" in data
        assert "math-add" in data["disabled"]
        assert "tools" in data

    def test_import_state(self, server_with_tools) -> None:
        """Test POST /api/state endpoint."""
        server, info = server_with_tools
        # Tool names are normalized to use hyphens
        tool_name = "math-add"

        # Import state with disabled tool
        state = {"disabled": {"math-add": "Imported reason"}}
        status, data = self._request(
            f"{info.url}/api/state",
            method="POST",
            data=state,
        )
        assert status == 200
        assert data["success"] is True

        # Verify tool is disabled
        status, data = self._request(f"{info.url}/api/tools/{tool_name}")
        assert data["enabled"] is False
        assert data["reason"] == "Imported reason"

    def test_import_state_rejects_bad_disabled_without_data_loss(
        self, server_with_tools
    ) -> None:
        """A malformed import must not clear the existing disabled set."""
        server, info = server_with_tools

        self._request(
            f"{info.url}/api/tools/math-add/disable",
            method="POST",
            data={"reason": "keep me"},
        )

        status, data = self._request(
            f"{info.url}/api/state",
            method="POST",
            data={"disabled": "not-a-dict"},
        )
        assert status == 400
        assert "disabled" in data["message"]

        status, data = self._request(f"{info.url}/api/tools/math-add")
        assert data["enabled"] is False
        assert data["reason"] == "keep me"

    def test_import_state_rejects_non_string_reasons(self, server_with_tools) -> None:
        """Reasons in the disabled map must be strings."""
        server, info = server_with_tools

        status, data = self._request(
            f"{info.url}/api/state",
            method="POST",
            data={"disabled": {"math-add": 123}},
        )
        assert status == 400
        assert "strings" in data["message"]

    def test_logs_without_logging_enabled(self, server_with_tools) -> None:
        """Test GET /api/logs when logging is not enabled."""
        server, info = server_with_tools
        status, data = self._request(f"{info.url}/api/logs")

        assert status == 400
        assert "Logging Disabled" in data["error"]

    def test_root_returns_ui(self, server_with_tools) -> None:
        """Test GET / returns HTML UI."""
        server, info = server_with_tools

        req = urllib.request.Request(f"{info.url}/")
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read().decode()
            assert "<!DOCTYPE html>" in content
            assert "ToolRegistry Admin Panel" in content

    def test_not_found(self, server_with_tools) -> None:
        """Test 404 for unknown paths."""
        server, info = server_with_tools
        status, data = self._request(f"{info.url}/api/unknown")

        assert status == 404
        assert "Not Found" in data["error"]


class TestAdminServerAuth:
    """Tests for authentication."""

    def test_auth_required_when_enabled(self) -> None:
        """Test that auth is required when token is set."""
        registry = ToolRegistry()
        server = AdminServer(registry, port=18085, auth_token="secret123")

        try:
            info = server.start()
            time.sleep(0.1)

            # Request without token should fail
            req = urllib.request.Request(f"{info.url}/api/tools")
            try:
                urllib.request.urlopen(req, timeout=5)
                pytest.fail("Should have raised HTTPError")
            except urllib.error.HTTPError as e:
                assert e.code == 401

            # Request with correct token should succeed
            req = urllib.request.Request(f"{info.url}/api/tools")
            req.add_header("Authorization", "Bearer secret123")
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200

        finally:
            server.stop()

    def test_auth_with_wrong_token(self) -> None:
        """Test that wrong token is rejected."""
        registry = ToolRegistry()
        server = AdminServer(registry, port=18086, auth_token="correct")

        try:
            info = server.start()
            time.sleep(0.1)

            req = urllib.request.Request(f"{info.url}/api/tools")
            req.add_header("Authorization", "Bearer wrong")
            try:
                urllib.request.urlopen(req, timeout=5)
                pytest.fail("Should have raised HTTPError")
            except urllib.error.HTTPError as e:
                assert e.code == 401

        finally:
            server.stop()

    def test_ui_shell_is_public_so_the_token_prompt_can_run(self) -> None:
        """GET / stays reachable without a token when the UI is enabled.

        The browser cannot attach an Authorization header to a top-level
        navigation, and the shell carries no registry data.  API routes must
        still require credentials.
        """
        registry = ToolRegistry()
        server = AdminServer(registry, port=18108, auth_token="secret123")

        try:
            info = server.start()
            time.sleep(0.1)

            req = urllib.request.Request(f"{info.url}/")
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200
                assert "ToolRegistry Admin Panel" in response.read().decode()

            req = urllib.request.Request(f"{info.url}/api/tools")
            try:
                urllib.request.urlopen(req, timeout=5)
                pytest.fail("Should have raised HTTPError")
            except urllib.error.HTTPError as e:
                assert e.code == 401

        finally:
            server.stop()

    def test_api_index_is_protected_when_ui_is_disabled(self) -> None:
        """With serve_ui=False, "/" is an API index and requires a token."""
        registry = ToolRegistry()
        server = AdminServer(
            registry, port=18109, serve_ui=False, auth_token="secret123"
        )

        try:
            info = server.start()
            time.sleep(0.1)

            req = urllib.request.Request(f"{info.url}/")
            try:
                urllib.request.urlopen(req, timeout=5)
                pytest.fail("Should have raised HTTPError")
            except urllib.error.HTTPError as e:
                assert e.code == 401

            req = urllib.request.Request(f"{info.url}/")
            req.add_header("Authorization", "Bearer secret123")
            with urllib.request.urlopen(req, timeout=5) as response:
                assert response.status == 200
                assert b"ToolRegistry Admin API" in response.read()

        finally:
            server.stop()


class TestToolRegistryAdminIntegration:
    """Tests for ToolRegistry admin integration methods."""

    def test_enable_admin(self) -> None:
        """Test enable_admin method."""
        registry = ToolRegistry()

        try:
            info = registry.enable_admin(port=18087)
            assert isinstance(info, AdminInfo)
            assert info.port == 18087
            assert registry.get_admin_info() is not None
        finally:
            registry.disable_admin()

    def test_disable_admin(self) -> None:
        """Test disable_admin method."""
        registry = ToolRegistry()

        registry.enable_admin(port=18088)
        registry.disable_admin()

        assert registry.get_admin_info() is None

    def test_enable_admin_already_running(self) -> None:
        """Test enable_admin when already running raises error."""
        registry = ToolRegistry()

        try:
            registry.enable_admin(port=18089)
            with pytest.raises(RuntimeError, match="already running"):
                registry.enable_admin(port=18089)
        finally:
            registry.disable_admin()

    def test_get_admin_info_not_running(self) -> None:
        """Test get_admin_info when not running returns None."""
        registry = ToolRegistry()
        assert registry.get_admin_info() is None

    def test_disable_admin_when_not_running(self) -> None:
        """Test disable_admin when not running is safe."""
        registry = ToolRegistry()
        # Should not raise
        registry.disable_admin()


class TestAdminServerWithLogging:
    """Tests for admin server with execution logging enabled."""

    @pytest.fixture
    def server_with_logging(self):
        """Create a server with logging enabled."""
        registry = ToolRegistry()
        registry.enable_logging(max_entries=100)

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        registry.register(add, namespace="math")

        server = AdminServer(registry, port=18091)
        info = server.start()
        time.sleep(0.1)

        yield server, info, registry

        server.stop()

    def _request(
        self,
        url: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> tuple[int, dict]:
        """Make HTTP request and return status code and JSON response."""
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_get_logs(self, server_with_logging) -> None:
        """Test GET /api/logs endpoint."""
        server, info, registry = server_with_logging

        status, data = self._request(f"{info.url}/api/logs")
        assert status == 200
        assert "entries" in data
        assert "count" in data

    def test_get_log_stats(self, server_with_logging) -> None:
        """Test GET /api/logs/stats endpoint."""
        server, info, registry = server_with_logging

        status, data = self._request(f"{info.url}/api/logs/stats")
        assert status == 200
        assert "total_entries" in data
        assert "by_status" in data

    def test_clear_logs(self, server_with_logging) -> None:
        """Test DELETE /api/logs endpoint."""
        server, info, registry = server_with_logging

        status, data = self._request(f"{info.url}/api/logs", method="DELETE")
        assert status == 200
        assert data["success"] is True


class TestAdminServerEnrichedAPI:
    """Tests for enriched API responses with metadata and permissions."""

    @pytest.fixture
    def server_with_metadata(self):
        """Create a server with tools that have rich metadata."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        def search(query: str) -> str:
            """Search the web."""
            return f"Results for {query}"

        registry.register(add, namespace="math")
        registry.register(search, namespace="web")

        # Set metadata on tools
        # Use private helper — these metadata fields aren't in the
        # public update_tool_metadata allowlist.
        registry._replace_tool_metadata(
            "math-add",
            tags={ToolTag.READ_ONLY},
            locality="local",
            timeout=30.0,
            think_augment=True,
        )

        # Use private helper — these metadata fields aren't in the
        # public update_tool_metadata allowlist.
        registry._replace_tool_metadata(
            "web-search",
            tags={ToolTag.NETWORK, ToolTag.SLOW},
            custom_tags={"external"},
            locality="remote",
            defer=True,
            search_hint="web query",
        )

        server = AdminServer(registry, port=18092)
        info = server.start()
        time.sleep(0.1)

        yield server, info, registry

        server.stop()

    def _request(
        self,
        url: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> tuple[int, dict]:
        """Make HTTP request and return status code and JSON response."""
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_get_tools_includes_metadata_fields(self, server_with_metadata) -> None:
        """Test GET /api/tools includes tags, locality, is_async, think_augment, defer."""
        server, info, registry = server_with_metadata
        status, data = self._request(f"{info.url}/api/tools")

        assert status == 200
        tools = {t["name"]: t for t in data["tools"]}

        add_tool = tools["math-add"]
        assert add_tool["tags"] == ["read_only"]
        assert add_tool["locality"] == "local"
        assert add_tool["is_async"] is False
        assert add_tool["think_augment"] is True
        assert add_tool["defer"] is False

        search_tool = tools["web-search"]
        assert sorted(search_tool["tags"]) == ["external", "network", "slow"]
        assert search_tool["locality"] == "remote"
        assert search_tool["defer"] is True

    def test_get_tool_detail_includes_full_metadata(self, server_with_metadata) -> None:
        """Test GET /api/tools/{name} includes full metadata object."""
        server, info, registry = server_with_metadata
        status, data = self._request(f"{info.url}/api/tools/math-add")

        assert status == 200
        assert "metadata" in data

        meta = data["metadata"]
        assert meta["is_async"] is False
        assert meta["is_concurrency_safe"] is True
        assert meta["timeout"] == 30.0
        assert meta["locality"] == "local"
        assert meta["max_result_size"] is None
        assert meta["tags"] == ["ToolTag.READ_ONLY"]
        assert meta["custom_tags"] == []
        assert meta["defer"] is False
        assert meta["search_hint"] == ""
        assert meta["think_augment"] is True
        assert meta["extra"] == {}

    def test_get_tool_detail_search_tool_metadata(self, server_with_metadata) -> None:
        """Test GET /api/tools/{name} for tool with custom tags and defer."""
        server, info, registry = server_with_metadata
        status, data = self._request(f"{info.url}/api/tools/web-search")

        assert status == 200
        meta = data["metadata"]
        assert meta["locality"] == "remote"
        assert meta["defer"] is True
        assert meta["search_hint"] == "web query"
        assert "external" in meta["custom_tags"]
        assert sorted(str(t) for t in meta["tags"]) == [
            "ToolTag.NETWORK",
            "ToolTag.SLOW",
        ]

    def test_get_namespaces_includes_tags(self, server_with_metadata) -> None:
        """Test GET /api/namespaces includes tags and metadata counts."""
        server, info, registry = server_with_metadata
        status, data = self._request(f"{info.url}/api/namespaces")

        assert status == 200
        ns_map = {ns["name"]: ns for ns in data["namespaces"]}

        math_ns = ns_map["math"]
        assert "read_only" in math_ns["tags"]
        assert math_ns["async_count"] == 0
        assert math_ns["remote_count"] == 0

        web_ns = ns_map["web"]
        assert "network" in web_ns["tags"]
        assert "external" in web_ns["tags"]
        assert web_ns["remote_count"] == 1

    def test_get_permissions_no_policy(self, server_with_metadata) -> None:
        """Test GET /api/permissions when no policy is set."""
        server, info, registry = server_with_metadata
        status, data = self._request(f"{info.url}/api/permissions")

        assert status == 200
        assert data["has_policy"] is False
        assert data["rules"] == []
        assert data["has_handler"] is False

    def test_get_permissions_with_policy(self, server_with_metadata) -> None:
        """Test GET /api/permissions with a policy set."""
        server, info, registry = server_with_metadata

        policy = PermissionPolicy(
            rules=[
                PermissionRule(
                    name="allow_readonly",
                    match=lambda t, p: ToolTag.READ_ONLY in t.metadata.tags,
                    result=PermissionResult.ALLOW,
                    reason="Read-only tools are safe",
                ),
                PermissionRule(
                    name="deny_network",
                    match=lambda t, p: ToolTag.NETWORK in t.metadata.tags,
                    result=PermissionResult.DENY,
                    reason="Network tools need review",
                ),
            ],
            fallback=PermissionResult.ASK,
        )
        registry.set_permission_policy(policy)

        status, data = self._request(f"{info.url}/api/permissions")

        assert status == 200
        assert data["has_policy"] is True
        assert data["fallback"] == "ask"
        assert data["has_handler"] is False
        assert len(data["rules"]) == 2

        assert data["rules"][0]["name"] == "allow_readonly"
        assert data["rules"][0]["result"] == "allow"
        assert data["rules"][0]["reason"] == "Read-only tools are safe"

        assert data["rules"][1]["name"] == "deny_network"
        assert data["rules"][1]["result"] == "deny"

    def test_get_tools_includes_permission(self, server_with_metadata) -> None:
        """Test GET /api/tools includes permission evaluation for each tool."""
        server, info, registry = server_with_metadata

        # Without policy, permission should be None
        status, data = self._request(f"{info.url}/api/tools")
        assert status == 200
        tools = {t["name"]: t for t in data["tools"]}
        assert tools["math-add"]["permission"] is None

        # Set a policy
        policy = PermissionPolicy(
            rules=[
                PermissionRule(
                    name="allow_readonly",
                    match=lambda t, p: ToolTag.READ_ONLY in t.metadata.tags,
                    result=PermissionResult.ALLOW,
                    reason="Read-only tools are safe",
                ),
                PermissionRule(
                    name="deny_network",
                    match=lambda t, p: ToolTag.NETWORK in t.metadata.tags,
                    result=PermissionResult.DENY,
                    reason="Network tools need review",
                ),
            ],
            fallback=PermissionResult.ASK,
        )
        registry.set_permission_policy(policy)

        status, data = self._request(f"{info.url}/api/tools")
        assert status == 200
        tools = {t["name"]: t for t in data["tools"]}

        # math-add has READ_ONLY tag → allow
        add_perm = tools["math-add"]["permission"]
        assert add_perm["result"] == "allow"
        assert add_perm["rule_name"] == "allow_readonly"

        # web-search has NETWORK tag → deny (first-match-wins, but also has no READ_ONLY)
        search_perm = tools["web-search"]["permission"]
        assert search_perm["result"] == "deny"
        assert search_perm["rule_name"] == "deny_network"

    def test_get_tool_detail_includes_permission(self, server_with_metadata) -> None:
        """Test GET /api/tools/{name} includes permission evaluation."""
        server, info, registry = server_with_metadata

        # Set a policy
        policy = PermissionPolicy(
            rules=[
                PermissionRule(
                    name="allow_readonly",
                    match=lambda t, p: ToolTag.READ_ONLY in t.metadata.tags,
                    result=PermissionResult.ALLOW,
                    reason="Read-only tools are safe",
                ),
            ],
            fallback=PermissionResult.ASK,
        )
        registry.set_permission_policy(policy)

        # math-add matches allow_readonly
        status, data = self._request(f"{info.url}/api/tools/math-add")
        assert status == 200
        assert data["permission"]["result"] == "allow"
        assert data["permission"]["rule_name"] == "allow_readonly"
        assert data["permission"]["reason"] == "Read-only tools are safe"

        # web-search doesn't match any rule → fallback (ask)
        status, data = self._request(f"{info.url}/api/tools/web-search")
        assert status == 200
        assert data["permission"]["result"] == "ask"
        assert data["permission"]["rule_name"] is None


class TestAdminServerMetadataUpdate:
    """Tests for PATCH /api/tools/{name}/metadata and PATCH /api/namespaces/{ns}/metadata."""

    @pytest.fixture
    def server_with_tools(self):
        """Create a server with tools for metadata update testing."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        registry.register(add, namespace="math")
        registry.register(multiply, namespace="math")
        registry.register(greet)

        server = AdminServer(registry, port=18093)
        info = server.start()
        time.sleep(0.1)

        yield server, info, registry

        server.stop()

    def _request(
        self,
        url: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> tuple[int, dict]:
        """Make HTTP request and return status code and JSON response."""
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_update_tool_think_augment(self, server_with_tools) -> None:
        """Test PATCH /api/tools/{name}/metadata with think_augment."""
        server, info, registry = server_with_tools

        # Initially think_augment is None/False
        tool = registry.get_tool("math-add")
        assert not tool.metadata.think_augment

        # Enable think_augment
        status, data = self._request(
            f"{info.url}/api/tools/math-add/metadata",
            method="PATCH",
            data={"think_augment": True},
        )
        assert status == 200
        assert data["success"] is True
        assert data["updated"] == {"think_augment": True}

        # Verify the metadata was actually updated (re-fetch; frozen tools
        # are replaced in the registry, so the old reference is stale)
        tool = registry.get_tool("math-add")
        assert tool.metadata.think_augment is True

    def test_update_tool_defer(self, server_with_tools) -> None:
        """Test PATCH /api/tools/{name}/metadata with defer."""
        server, info, registry = server_with_tools

        tool = registry.get_tool("greet")
        assert tool.metadata.defer is False

        status, data = self._request(
            f"{info.url}/api/tools/greet/metadata",
            method="PATCH",
            data={"defer": True},
        )
        assert status == 200
        assert data["success"] is True
        tool = registry.get_tool("greet")
        assert tool.metadata.defer is True

    def test_update_tool_invalid_field(self, server_with_tools) -> None:
        """Test PATCH with disallowed field returns 400."""
        server, info, registry = server_with_tools

        status, data = self._request(
            f"{info.url}/api/tools/math-add/metadata",
            method="PATCH",
            data={"is_async": True},
        )
        assert status == 400
        assert "not allowed" in data["message"]

    def test_update_tool_unknown_tool(self, server_with_tools) -> None:
        """Test PATCH on nonexistent tool returns 404."""
        server, info, registry = server_with_tools

        status, data = self._request(
            f"{info.url}/api/tools/nonexistent/metadata",
            method="PATCH",
            data={"think_augment": True},
        )
        assert status == 404

    def test_update_tool_empty_body(self, server_with_tools) -> None:
        """Test PATCH with empty body returns 400."""
        server, info, registry = server_with_tools

        status, data = self._request(
            f"{info.url}/api/tools/math-add/metadata",
            method="PATCH",
            data={},
        )
        assert status == 400

    def test_update_namespace_metadata(self, server_with_tools) -> None:
        """Test PATCH /api/namespaces/{ns}/metadata updates all tools."""
        server, info, registry = server_with_tools

        tool_add = registry.get_tool("math-add")
        tool_mul = registry.get_tool("math-multiply")
        assert not tool_add.metadata.think_augment
        assert not tool_mul.metadata.think_augment

        status, data = self._request(
            f"{info.url}/api/namespaces/math/metadata",
            method="PATCH",
            data={"think_augment": True},
        )
        assert status == 200
        assert data["success"] is True
        assert data["tools_updated"] == 2

        # Both tools should be updated (re-fetch; frozen replacement)
        tool_add = registry.get_tool("math-add")
        tool_mul = registry.get_tool("math-multiply")
        assert tool_add.metadata.think_augment is True
        assert tool_mul.metadata.think_augment is True

    def test_update_namespace_unknown(self, server_with_tools) -> None:
        """Test PATCH on nonexistent namespace returns 404."""
        server, info, registry = server_with_tools

        status, data = self._request(
            f"{info.url}/api/namespaces/nonexistent/metadata",
            method="PATCH",
            data={"defer": True},
        )
        assert status == 404


class TestAdminSourcesAndConfig:
    """Tests for source info, /api/sources, and /api/config endpoints."""

    @pytest.fixture
    def server_with_tools(self):
        """Create a server with registered tools."""
        registry = ToolRegistry()

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        def subtract(a: int, b: int) -> int:
            """Subtract two numbers."""
            return a - b

        registry.register(add, namespace="math")
        registry.register(subtract, namespace="math")

        server = AdminServer(registry, port=18094)
        info = server.start()
        time.sleep(0.1)

        yield server, info, registry

        server.stop()

    def _request(
        self,
        url: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> tuple[int, dict]:
        """Make HTTP request and return status code and JSON response."""
        headers = {"Content-Type": "application/json"}
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_get_tools_includes_source(self, server_with_tools) -> None:
        """Test GET /api/tools includes source and source_detail fields."""
        server, info, registry = server_with_tools
        status, data = self._request(f"{info.url}/api/tools")
        assert status == 200
        for tool in data["tools"]:
            assert "source" in tool
            assert "source_detail" in tool
            assert tool["source"] == "native"

    def test_get_tool_detail_includes_source(self, server_with_tools) -> None:
        """Test GET /api/tools/{name} includes source in metadata."""
        server, info, registry = server_with_tools
        status, data = self._request(f"{info.url}/api/tools/math-add")
        assert status == 200
        assert "source" in data["metadata"]
        assert "source_detail" in data["metadata"]
        assert data["metadata"]["source"] == "native"

    def test_get_sources(self, server_with_tools) -> None:
        """Test GET /api/sources returns aggregated source info."""
        server, info, registry = server_with_tools
        status, data = self._request(f"{info.url}/api/sources")
        assert status == 200
        assert "sources" in data
        assert len(data["sources"]) >= 1
        src = data["sources"][0]
        assert "type" in src
        assert "detail" in src
        assert "namespace" in src
        assert "tool_count" in src
        assert "enabled_count" in src
        assert "tools" in src
        assert src["type"] == "native"
        assert src["tool_count"] == 2

    def test_export_state_includes_sources(self, server_with_tools) -> None:
        """Test GET /api/state includes sources in export."""
        server, info, registry = server_with_tools
        status, data = self._request(f"{info.url}/api/state")
        assert status == 200
        assert "sources" in data
        assert "math-add" in data["sources"]
        assert data["sources"]["math-add"]["source"] == "native"

    def test_get_config_no_config(self, server_with_tools) -> None:
        """Test GET /api/config returns 404 when no config loaded."""
        server, info, registry = server_with_tools
        status, data = self._request(f"{info.url}/api/config")
        assert status == 404

    def test_config_endpoints_with_config(self, tmp_path) -> None:
        """Test GET/PUT /api/config with a loaded config."""
        from toolregistry.config import ToolConfig, PythonSource, load_config

        config = ToolConfig(
            mode="denylist",
            disabled=("ns1",),
            tools=(PythonSource(class_path="a.B", namespace="calc"),),
            source=str(tmp_path / "tools.json"),
        )
        # Write initial config file
        config_path = tmp_path / "tools.json"
        config_path.write_text('{"mode": "denylist", "disabled": ["ns1"]}')

        registry = ToolRegistry()
        registry.register(lambda x: x, name="echo")
        server = AdminServer(registry, port=18095, config=config)
        info = server.start()
        time.sleep(0.1)

        try:
            # GET /api/config
            status, data = self._request(f"{info.url}/api/config")
            assert status == 200
            assert data["mode"] == "denylist"
            assert "ns1" in data["disabled"]
            assert data["source"] == str(config_path)

            # PUT /api/config — update disabled list
            status, data = self._request(
                f"{info.url}/api/config",
                method="PUT",
                data={"disabled": ["ns1", "ns2"]},
            )
            assert status == 200
            assert data["saved"] is True
            assert "ns2" in data["disabled"]

            # Verify file was written
            reloaded = load_config(config_path)
            assert "ns2" in reloaded.disabled

            # GET /api/config should reflect update
            status, data = self._request(f"{info.url}/api/config")
            assert status == 200
            assert "ns2" in data["disabled"]
        finally:
            server.stop()

    def test_update_config_invalid_mode(self, tmp_path) -> None:
        """Test PUT /api/config rejects invalid mode."""
        from toolregistry.config import ToolConfig

        config = ToolConfig(source=str(tmp_path / "tools.json"))
        (tmp_path / "tools.json").write_text('{"mode": "denylist"}')

        registry = ToolRegistry()
        server = AdminServer(registry, port=18096, config=config)
        info = server.start()
        time.sleep(0.1)

        try:
            status, data = self._request(
                f"{info.url}/api/config",
                method="PUT",
                data={"mode": "invalid"},
            )
            assert status == 400
        finally:
            server.stop()

    def test_update_config_name_sep_uses_validating_setter(self, tmp_path) -> None:
        """PUT /api/config validates name_sep through the registry setter."""
        from toolregistry.config import ToolConfig

        config = ToolConfig(source=str(tmp_path / "tools.json"))
        (tmp_path / "tools.json").write_text('{"mode": "denylist"}')

        registry = ToolRegistry()
        server = AdminServer(registry, port=18097, config=config)
        info = server.start()
        time.sleep(0.1)

        try:
            status, _ = self._request(
                f"{info.url}/api/config",
                method="PUT",
                data={"name_sep": "."},
            )
            assert status == 200
            assert registry.name_sep == "."

            status, data = self._request(
                f"{info.url}/api/config",
                method="PUT",
                data={"name_sep": "_"},
            )
            assert status == 400
            assert data["message"] == "name_sep must be '-' or '.'"
            assert registry.name_sep == "."
        finally:
            server.stop()


class TestRequestMetrics:
    """Unit tests for the RequestMetrics collector."""

    @staticmethod
    def _request_state(path: str = "/api/tools") -> SimpleNamespace:
        return SimpleNamespace(state=SimpleNamespace(), path=path)

    def test_counts_and_latency_summary(self) -> None:
        metrics = RequestMetrics()
        request = self._request_state()

        metrics.before_request(request)
        metrics.response_started(request, None)
        metrics.response_completed(request, None)
        metrics.client_disconnect(request)

        snapshot = metrics.snapshot()
        assert snapshot["requests_total"] == 1
        assert snapshot["responses_started"] == 1
        assert snapshot["responses_completed"] == 1
        assert snapshot["client_disconnects"] == 1
        assert snapshot["ttfb"]["count"] == 1
        assert snapshot["duration"]["count"] == 1
        assert snapshot["ttfb"]["p95_ms"] >= 0
        assert snapshot["duration"]["max_ms"] >= 0
        assert snapshot["uptime_seconds"] >= 0

    def test_empty_summary_is_json_safe(self) -> None:
        snapshot = RequestMetrics().snapshot()
        assert snapshot["requests_total"] == 0
        assert snapshot["ttfb"] == {
            "count": 0,
            "avg_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None,
        }
        assert snapshot["duration"]["count"] == 0

    def test_sample_buffer_is_bounded(self) -> None:
        metrics = RequestMetrics(sample_size=2)
        for _ in range(3):
            request = self._request_state()
            metrics.before_request(request)
            metrics.response_completed(request, None)
        assert metrics.snapshot()["duration"]["count"] == 2

    def test_metrics_scrapes_are_counted_but_not_sampled(self) -> None:
        metrics = RequestMetrics()

        traffic = self._request_state("/api/tools")
        metrics.before_request(traffic)
        metrics.response_started(traffic, None)
        metrics.response_completed(traffic, None)

        scrape = self._request_state("/api/metrics")
        metrics.before_request(scrape)
        metrics.response_started(scrape, None)
        metrics.response_completed(scrape, None)

        snapshot = metrics.snapshot()
        assert snapshot["requests_total"] == 2
        assert snapshot["responses_started"] == 2
        assert snapshot["responses_completed"] == 2
        assert snapshot["ttfb"]["count"] == 1
        assert snapshot["duration"]["count"] == 1

    def test_metrics_handler_reports_unavailable(self) -> None:
        """An AdminApp served without start() has no metrics collector."""
        from toolregistry.admin.handlers import _get_metrics
        from toolregistry.admin.server import AdminApp

        app = AdminApp()
        app.metrics = None
        response = _get_metrics(SimpleNamespace(app=app))

        assert response.status_code == 503
        assert b"Metrics Unavailable" in response.body


class TestAdminServerMetrics:
    """Integration tests for the /api/metrics endpoint."""

    @pytest.fixture
    def metrics_server(self):
        registry = ToolRegistry()
        server = AdminServer(registry, port=18100)
        info = server.start()
        time.sleep(0.1)
        yield server, info
        server.stop()

    @staticmethod
    def _get(url: str) -> tuple[int, dict]:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, json.loads(response.read().decode())

    def test_metrics_endpoint_reports_request_activity(self, metrics_server) -> None:
        server, info = metrics_server

        status, _ = self._get(f"{info.url}/api/tools")
        assert status == 200

        status, data = self._get(f"{info.url}/api/metrics")
        assert status == 200
        assert data["requests_total"] >= 2
        assert data["responses_started"] >= 1
        assert data["responses_completed"] >= 1
        assert data["ttfb"]["count"] >= 1
        assert data["duration"]["count"] >= 1
        assert data["uptime_seconds"] >= 0

    def test_metrics_endpoint_is_listed(self, metrics_server) -> None:
        server, info = metrics_server
        status, data = self._get(f"{info.url}/api/metrics")
        assert status == 200
        assert "requests_total" in data

    @pytest.fixture
    def auth_metrics_server(self):
        registry = ToolRegistry()
        server = AdminServer(registry, port=18103, auth_token="metrics-secret")
        info = server.start()
        time.sleep(0.1)
        yield server, info
        server.stop()

    def test_rejected_requests_are_counted_and_timed(self, auth_metrics_server) -> None:
        """The timing hook must run before auth rejects the request."""
        server, info = auth_metrics_server

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{info.url}/api/tools", timeout=5)
        assert exc_info.value.code == 401

        request = urllib.request.Request(
            f"{info.url}/api/metrics",
            headers={"Authorization": "Bearer metrics-secret"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode())

        assert data["requests_total"] == 2
        assert data["responses_started"] == 1
        assert data["responses_completed"] == 1
        # A reordered hook would leave metrics_start unset for the 401.
        assert data["ttfb"]["count"] == data["responses_started"]
        assert data["duration"]["count"] == data["responses_completed"]

    def test_ephemeral_port_is_reported(self) -> None:
        """port=0 must report the actual bound port, not 0."""
        server = AdminServer(ToolRegistry(), port=0)
        try:
            info = server.start()
            assert info.port > 0
            assert f":{info.port}" in info.url
            status, data = self._get(f"{info.url}/api/tools")
            assert status == 200
            assert "tools" in data
        finally:
            server.stop()


class TestAdminServerTLS:
    """TLS configuration, handshake, and startup failure tests."""

    @pytest.fixture
    def server_tls_context(self, tmp_path):
        openssl = shutil.which("openssl")
        if openssl is None:
            pytest.skip("openssl is required for the TLS integration test")

        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            capture_output=True,
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert), str(key))
        return context

    def test_default_url_is_http(self) -> None:
        server = AdminServer(ToolRegistry())
        assert server.ssl_context is None
        assert server._base_url().startswith("http://")

    def test_ssl_context_switches_url_scheme(self) -> None:
        context = ssl.create_default_context()
        server = AdminServer(ToolRegistry(), ssl_context=context)
        assert server.ssl_context is context
        assert server._base_url().startswith("https://")

    def test_running_info_reports_secure_flag(self) -> None:
        server = AdminServer(ToolRegistry(), port=18101)
        try:
            info = server.start()
            assert info.secure is False
            assert info.url.startswith("http://")
        finally:
            server.stop()

    @pytest.mark.asyncio
    async def test_async_serve_passes_ssl_context(self, monkeypatch) -> None:
        """The TLS context must reach asyncio.start_server."""
        from toolregistry.admin.server import AdminApp

        server = AdminServer(ToolRegistry(), ssl_context=ssl.create_default_context())
        server._port = 18102

        app = AdminApp()
        app.registry = server.registry
        app.auth = None
        app.session = None
        app.serve_ui = False
        app.config = None
        server._app = app

        recorded: dict = {}

        class FakeServer:
            sockets: list = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        async def fake_start_server(*args, **kwargs):
            recorded["kwargs"] = kwargs
            assert app._shutdown_event is not None
            app._shutdown_event.set()
            return FakeServer()

        monkeypatch.setattr(asyncio, "start_server", fake_start_server)
        await server._async_serve()

        assert recorded["kwargs"]["ssl"] is server.ssl_context

    def test_https_serves_and_reports_secure(self, server_tls_context) -> None:
        server = AdminServer(ToolRegistry(), port=18104, ssl_context=server_tls_context)
        try:
            info = server.start()
            assert info.secure is True
            assert info.url.startswith("https://")

            client = ssl.create_default_context()
            client.check_hostname = False
            client.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(
                f"{info.url}/api/tools", timeout=5, context=client
            ) as response:
                assert response.status == 200
                assert "tools" in json.loads(response.read().decode())
        finally:
            server.stop()

    def test_start_rejects_context_without_certificate(self) -> None:
        """A context that cannot serve TLS must not report a healthy server."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server = AdminServer(ToolRegistry(), port=18105, ssl_context=context)

        with pytest.raises(RuntimeError, match="failed to start") as exc_info:
            server.start()

        assert "TLS handshake failed" in str(exc_info.value.__cause__)
        assert not server.is_running()
        assert server._thread is None
        server.stop()

    def test_start_timeout_keeps_late_listener_reachable(self, monkeypatch) -> None:
        """A listener that binds after the timeout must still be stoppable."""
        real_start_server = asyncio.start_server

        async def slow_start_server(*args, **kwargs):
            await asyncio.sleep(0.3)
            return await real_start_server(*args, **kwargs)

        monkeypatch.setattr(asyncio, "start_server", slow_start_server)
        monkeypatch.setattr(AdminServer, "_START_TIMEOUT_SECONDS", 0.05)

        server = AdminServer(ToolRegistry(), port=18106)
        with pytest.raises(RuntimeError, match="did not start"):
            server.start()

        # The references are kept while the thread is alive, so stop() can
        # still reach the listener that binds after start() gave up.
        assert server._thread is not None
        deadline = time.monotonic() + 2.0
        while server._thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not server._thread.is_alive()

        server.stop()
        assert server._thread is None
        assert server._app is None
        assert not server.is_running()


class TestAdminJSONBody:
    """Admin responses must stay valid JSON whatever a tool returns (#348).

    The panel builds its own bodies, so it never went through the vendored
    ``JSONResponse`` that writes non-finite floats as ``null``.  ``NaN`` would
    reach the browser as a bare constant and ``JSON.parse`` would reject the
    whole response.
    """

    def test_non_finite_floats_are_written_as_null(self) -> None:
        from toolregistry.admin.handlers import _json_response

        response = _json_response(
            {"loss": float("nan"), "up": float("inf"), "down": float("-inf"), "ok": 1.5}
        )

        assert json.loads(response.body) == {
            "loss": None,
            "up": None,
            "down": None,
            "ok": 1.5,
        }

    def test_nested_non_finite_floats_are_written_as_null(self) -> None:
        from toolregistry.admin.handlers import _json_response

        response = _json_response({"entries": [{"metrics": [float("nan")]}]})

        assert json.loads(response.body) == {"entries": [{"metrics": [None]}]}

    def test_datetime_and_sets_still_serialize(self) -> None:
        from datetime import datetime

        from toolregistry.admin.handlers import _json_response

        response = _json_response(
            {"when": datetime(2024, 1, 2, 3, 4, 5), "tags": {"a"}}
        )

        assert json.loads(response.body) == {
            "when": "2024-01-02T03:04:05",
            "tags": ["a"],
        }

    def test_unsupported_object_raises_instead_of_emitting_invalid_json(self) -> None:
        from toolregistry.admin.handlers import _json_response

        with pytest.raises(TypeError):
            _json_response({"bad": object()})


class TestAdminNonFiniteToolResult:
    """A tool result holding ``NaN`` must not blank the log view (#348)."""

    @pytest.fixture
    def metric_server(self):
        registry = ToolRegistry()
        registry.enable_logging(max_entries=10)

        def metric() -> dict:
            """Return metrics computed from an empty set."""
            return {"loss": float("nan"), "ratio": float("inf")}

        registry.register(metric)
        registry.execute_tool_calls(
            [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "metric", "arguments": "{}"},
                }
            ]
        )

        server = AdminServer(registry, port=18107)
        info = server.start()
        time.sleep(0.1)

        yield info

        server.stop()

    def test_logs_endpoint_returns_parseable_json(self, metric_server) -> None:
        with urllib.request.urlopen(f"{metric_server.url}/api/logs", timeout=5) as resp:
            payload = json.loads(resp.read().decode())

        # The log stores the result as JSON text; the panel echoes it, so the
        # body must stay parseable end to end.
        assert json.loads(payload["entries"][0]["result"]) == {
            "loss": None,
            "ratio": None,
        }
