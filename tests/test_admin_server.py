"""Tests for admin panel server functionality.

This module tests the AdminServer, TokenAuth, and REST API endpoints.
"""

import json
import time
import urllib.request
import urllib.error

import pytest

from toolregistry import AdminInfo, AdminServer, TokenAuth, ToolRegistry


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
