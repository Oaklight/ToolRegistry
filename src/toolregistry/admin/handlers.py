"""HTTP request handlers for admin panel.

This module provides the HTTP request handler for the admin panel,
implementing REST API endpoints for tool management and monitoring.
"""

import json
import urllib.parse
from dataclasses import asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, Any, ClassVar

from .static import ADMIN_HTML

if TYPE_CHECKING:
    from toolregistry import ToolRegistry

    from .auth import TokenAuth


class AdminRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for admin panel.

    This handler implements REST API endpoints for:
    - Tool status and management (enable/disable)
    - Namespace management
    - Execution log queries and statistics
    - State export/import

    Class Attributes:
        registry: The ToolRegistry instance to manage.
        auth: Optional TokenAuth instance for authentication.
        serve_ui: Whether to serve the admin UI at root path.
    """

    # Class attributes set by AdminServer
    registry: ClassVar["ToolRegistry"]
    auth: ClassVar["TokenAuth | None"]
    serve_ui: ClassVar[bool]

    # Suppress default logging
    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        # Check authentication if enabled
        if self.auth and not self.auth.require_auth(self):
            return

        # Parse URL
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Route requests
        if path == "/":
            self._handle_root()
        elif path == "/api/tools":
            self._handle_get_tools()
        elif path.startswith("/api/tools/") and not path.endswith(
            ("/enable", "/disable")
        ):
            tool_name = path[len("/api/tools/") :]
            self._handle_get_tool(urllib.parse.unquote(tool_name))
        elif path == "/api/namespaces":
            self._handle_get_namespaces()
        elif path == "/api/logs":
            self._handle_get_logs(query)
        elif path == "/api/logs/stats":
            self._handle_get_log_stats()
        elif path == "/api/state":
            self._handle_export_state()
        else:
            self._send_not_found()

    def do_POST(self) -> None:
        """Handle POST requests."""
        # Check authentication if enabled
        if self.auth and not self.auth.require_auth(self):
            return

        # Parse URL
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        # Route requests
        if path.startswith("/api/tools/") and path.endswith("/enable"):
            tool_name = path[len("/api/tools/") : -len("/enable")]
            self._handle_enable_tool(urllib.parse.unquote(tool_name))
        elif path.startswith("/api/tools/") and path.endswith("/disable"):
            tool_name = path[len("/api/tools/") : -len("/disable")]
            self._handle_disable_tool(urllib.parse.unquote(tool_name), body)
        elif path.startswith("/api/namespaces/") and path.endswith("/enable"):
            namespace = path[len("/api/namespaces/") : -len("/enable")]
            self._handle_enable_namespace(urllib.parse.unquote(namespace))
        elif path.startswith("/api/namespaces/") and path.endswith("/disable"):
            namespace = path[len("/api/namespaces/") : -len("/disable")]
            self._handle_disable_namespace(urllib.parse.unquote(namespace), body)
        elif path == "/api/state":
            self._handle_import_state(body)
        else:
            self._send_not_found()

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        # Check authentication if enabled
        if self.auth and not self.auth.require_auth(self):
            return

        # Parse URL
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Route requests
        if path == "/api/logs":
            self._handle_clear_logs()
        else:
            self._send_not_found()

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    # ============== Response Helpers ==============

    def _send_cors_headers(self) -> None:
        """Send CORS headers for cross-origin requests."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json_response(
        self, data: Any, status: int = 200, message: str | None = None
    ) -> None:
        """Send a JSON response.

        Args:
            data: The data to serialize as JSON.
            status: HTTP status code.
            message: Optional status message.
        """
        self.send_response(status, message)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        response = json.dumps(data, default=self._json_serializer)
        self.wfile.write(response.encode("utf-8"))

    def _send_error_response(self, status: int, error: str, message: str) -> None:
        """Send an error response.

        Args:
            status: HTTP status code.
            error: Error type/name.
            message: Detailed error message.
        """
        self._send_json_response({"error": error, "message": message}, status)

    def _send_not_found(self) -> None:
        """Send a 404 Not Found response."""
        self._send_error_response(404, "Not Found", f"Path not found: {self.path}")

    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for non-standard types.

        Args:
            obj: Object to serialize.

        Returns:
            JSON-serializable representation.

        Raises:
            TypeError: If object is not serializable.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    # ============== Route Handlers ==============

    def _handle_root(self) -> None:
        """Handle root path - serve UI or redirect."""
        if self.serve_ui:
            # Return a simple admin panel UI
            html = self._get_admin_ui_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
        else:
            self._send_json_response(
                {
                    "name": "ToolRegistry Admin API",
                    "version": "1.0.0",
                    "endpoints": [
                        "GET /api/tools",
                        "GET /api/tools/{name}",
                        "POST /api/tools/{name}/enable",
                        "POST /api/tools/{name}/disable",
                        "GET /api/namespaces",
                        "POST /api/namespaces/{ns}/enable",
                        "POST /api/namespaces/{ns}/disable",
                        "GET /api/logs",
                        "GET /api/logs/stats",
                        "DELETE /api/logs",
                        "GET /api/state",
                        "POST /api/state",
                    ],
                }
            )

    def _handle_get_tools(self) -> None:
        """Handle GET /api/tools - get all tools status."""
        tools_status = self.registry.get_tools_status()
        self._send_json_response({"tools": tools_status})

    def _handle_get_tool(self, tool_name: str) -> None:
        """Handle GET /api/tools/{name} - get single tool details.

        Args:
            tool_name: Name of the tool to get.
        """
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            self._send_error_response(404, "Not Found", f"Tool not found: {tool_name}")
            return

        enabled = self.registry.is_enabled(tool_name)
        reason = self.registry.get_disable_reason(tool_name) if not enabled else None

        tool_info = {
            "name": tool.name,
            "namespace": tool.namespace,
            "method_name": tool.method_name,
            "description": tool.description,
            "enabled": enabled,
            "reason": reason,
            "schema": tool.get_json_schema(),
        }
        self._send_json_response(tool_info)

    def _handle_enable_tool(self, tool_name: str) -> None:
        """Handle POST /api/tools/{name}/enable - enable a tool.

        Args:
            tool_name: Name of the tool to enable.
        """
        if tool_name not in self.registry:
            self._send_error_response(404, "Not Found", f"Tool not found: {tool_name}")
            return

        self.registry.enable(tool_name)
        self._send_json_response(
            {"success": True, "message": f"Tool '{tool_name}' enabled"}
        )

    def _handle_disable_tool(self, tool_name: str, body: bytes) -> None:
        """Handle POST /api/tools/{name}/disable - disable a tool.

        Args:
            tool_name: Name of the tool to disable.
            body: Request body containing optional reason.
        """
        if tool_name not in self.registry:
            self._send_error_response(404, "Not Found", f"Tool not found: {tool_name}")
            return

        reason = ""
        if body:
            try:
                data = json.loads(body)
                reason = data.get("reason", "")
            except json.JSONDecodeError:
                pass

        self.registry.disable(tool_name, reason)
        self._send_json_response(
            {
                "success": True,
                "message": f"Tool '{tool_name}' disabled",
                "reason": reason,
            }
        )

    def _handle_get_namespaces(self) -> None:
        """Handle GET /api/namespaces - get all namespaces."""
        # Get unique namespaces from tools (including "default" for non-namespaced)
        namespaces: dict[str, dict[str, Any]] = {}
        for tool_name in self.registry.list_all_tools():
            tool = self.registry.get_tool(tool_name)
            if tool:
                ns = tool.namespace or "default"
                if ns not in namespaces:
                    namespaces[ns] = {
                        "name": ns,
                        "tool_count": 0,
                        "enabled_count": 0,
                        "disabled_count": 0,
                    }
                namespaces[ns]["tool_count"] += 1
                if self.registry.is_enabled(tool_name):
                    namespaces[ns]["enabled_count"] += 1
                else:
                    namespaces[ns]["disabled_count"] += 1

        # Sort: "default" first, then alphabetical
        result = sorted(
            namespaces.values(),
            key=lambda x: "" if x["name"] == "default" else x["name"],
        )
        self._send_json_response({"namespaces": result})

    def _handle_enable_namespace(self, namespace: str) -> None:
        """Handle POST /api/namespaces/{ns}/enable - enable all tools in namespace.

        Args:
            namespace: Namespace to enable.
        """
        # Enable the namespace itself (removes namespace-level disable)
        self.registry.enable(namespace)

        # Also enable individual tools in the namespace
        enabled_count = 0
        for tool_name in self.registry.list_all_tools():
            tool = self.registry.get_tool(tool_name)
            if tool and tool.namespace == namespace:
                self.registry.enable(tool_name)
                enabled_count += 1

        self._send_json_response(
            {
                "success": True,
                "message": f"Namespace '{namespace}' enabled",
                "tools_enabled": enabled_count,
            }
        )

    def _handle_disable_namespace(self, namespace: str, body: bytes) -> None:
        """Handle POST /api/namespaces/{ns}/disable - disable all tools in namespace.

        Args:
            namespace: Namespace to disable.
            body: Request body containing optional reason.
        """
        reason = ""
        if body:
            try:
                data = json.loads(body)
                reason = data.get("reason", "")
            except json.JSONDecodeError:
                pass

        # Disable at namespace level (affects all tools in namespace)
        self.registry.disable(namespace, reason)

        # Count affected tools
        affected_count = 0
        for tool_name in self.registry.list_all_tools():
            tool = self.registry.get_tool(tool_name)
            if tool and tool.namespace == namespace:
                affected_count += 1

        self._send_json_response(
            {
                "success": True,
                "message": f"Namespace '{namespace}' disabled",
                "tools_affected": affected_count,
                "reason": reason,
            }
        )

    def _handle_get_logs(self, query: dict[str, list[str]]) -> None:
        """Handle GET /api/logs - get execution logs.

        Args:
            query: Query parameters for filtering.
        """
        log = self.registry.get_execution_log()
        if log is None:
            self._send_error_response(
                400, "Logging Disabled", "Execution logging is not enabled"
            )
            return

        # Parse query parameters
        limit = int(query.get("limit", ["100"])[0])
        tool_name = query.get("tool_name", [None])[0]
        status_str = query.get("status", [None])[0]

        # Import ExecutionStatus for filtering
        from .execution_log import ExecutionStatus

        status = None
        if status_str:
            try:
                status = ExecutionStatus(status_str)
            except ValueError:
                pass

        entries = log.get_entries(limit=limit, tool_name=tool_name, status=status)

        # Convert entries to dicts
        entries_data = [asdict(entry) for entry in entries]

        self._send_json_response({"entries": entries_data, "count": len(entries_data)})

    def _handle_get_log_stats(self) -> None:
        """Handle GET /api/logs/stats - get execution statistics."""
        log = self.registry.get_execution_log()
        if log is None:
            self._send_error_response(
                400, "Logging Disabled", "Execution logging is not enabled"
            )
            return

        stats = log.get_stats()
        self._send_json_response(stats)

    def _handle_clear_logs(self) -> None:
        """Handle DELETE /api/logs - clear execution logs."""
        log = self.registry.get_execution_log()
        if log is None:
            self._send_error_response(
                400, "Logging Disabled", "Execution logging is not enabled"
            )
            return

        cleared = log.clear()
        self._send_json_response(
            {"success": True, "message": f"Cleared {cleared} log entries"}
        )

    def _handle_export_state(self) -> None:
        """Handle GET /api/state - export current state."""
        # Export disabled tools/namespaces
        state = {
            "disabled": dict(self.registry._disabled),
            "tools": self.registry.list_all_tools(),
        }
        self._send_json_response(state)

    def _handle_import_state(self, body: bytes) -> None:
        """Handle POST /api/state - import/restore state.

        Args:
            body: Request body containing state to restore.
        """
        if not body:
            self._send_error_response(400, "Bad Request", "Request body is required")
            return

        try:
            state = json.loads(body)
        except json.JSONDecodeError as e:
            self._send_error_response(400, "Bad Request", f"Invalid JSON: {e}")
            return

        # Restore disabled state
        if "disabled" in state:
            # Clear current disabled state
            self.registry._disabled.clear()
            # Restore from state
            for name, reason in state["disabled"].items():
                self.registry.disable(name, reason)

        self._send_json_response(
            {"success": True, "message": "State restored successfully"}
        )

    def _get_admin_ui_html(self) -> str:
        """Get the admin panel HTML UI.

        Returns:
            HTML string for the admin panel.
        """
        return ADMIN_HTML
