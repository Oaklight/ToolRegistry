"""HTTP request handlers for admin panel.

This module provides route registration for the admin panel using
the zerodep httpserver, implementing REST API endpoints for tool
management and monitoring.
"""

import json
import urllib.parse
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from .._vendor.httpserver import HTTPException, Request, Response

from .static import ADMIN_HTML

if TYPE_CHECKING:
    from toolregistry import ToolRegistry

    from .server import AdminApp


# ============== CORS Constants ==============

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


# ============== Request Helpers ==============


def _app(request: Request) -> "AdminApp":
    """Get the typed AdminApp from a request."""
    from .server import AdminApp

    return cast(AdminApp, request.app)


# ============== Response Helpers ==============


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


def _json_response(data: Any, status_code: int = 200) -> Response:
    """Create a JSON response with custom datetime serialization.

    Args:
        data: The data to serialize as JSON.
        status_code: HTTP status code.

    Returns:
        Response with JSON content type.
    """
    body = json.dumps(data, default=_json_serializer)
    return Response(
        body=body,
        status_code=status_code,
        content_type="application/json; charset=utf-8",
    )


def _error_response(status: int, error: str, message: str) -> Response:
    """Create an error JSON response.

    Args:
        status: HTTP status code.
        error: Error type/name.
        message: Detailed error message.

    Returns:
        Response with error details.
    """
    return _json_response({"error": error, "message": message}, status)


def _add_cors(response: Response) -> Response:
    """Add CORS headers to a response.

    Args:
        response: The response to add headers to.

    Returns:
        The response with CORS headers added.
    """
    response.headers.update(_CORS_HEADERS)
    return response


def _evaluate_tool_permission(
    registry: "ToolRegistry", tool_name: str
) -> dict[str, Any] | None:
    """Evaluate permission for a tool against the current policy.

    Args:
        registry: The ToolRegistry instance.
        tool_name: Name of the tool to evaluate.

    Returns:
        Dict with result, rule_name, and reason, or None if no policy.
    """
    policy = registry.get_permission_policy()
    if policy is None:
        return None

    tool = registry.get_tool(tool_name)
    if tool is None:
        return None

    from ..permissions import PermissionResult, PermissionRule

    result = policy.evaluate(tool, {})
    if isinstance(result, PermissionRule):
        return {
            "result": result.result.value,
            "rule_name": result.name,
            "reason": result.reason,
        }
    elif isinstance(result, PermissionResult):
        return {
            "result": result.value,
            "rule_name": None,
            "reason": "Fallback policy",
        }
    return None


# ============== Middleware Handlers ==============


def _cors_preflight(request: Request) -> Response | None:
    """Handle CORS preflight requests."""
    if request.method == "OPTIONS":
        return Response(status_code=204, headers=dict(_CORS_HEADERS))
    return None


def _auth_check(request: Request) -> Response | None:
    """Check authentication token if auth is enabled."""
    auth = _app(request).auth
    if auth is None:
        return None

    auth_header = request.headers.get("authorization", "")

    if not auth_header:
        resp = _error_response(401, "Unauthorized", "Missing Authorization header")
        resp.headers["WWW-Authenticate"] = 'Bearer realm="admin"'
        return _add_cors(resp)

    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        resp = _error_response(401, "Unauthorized", "Invalid Authorization format")
        resp.headers["WWW-Authenticate"] = 'Bearer realm="admin"'
        return _add_cors(resp)

    if not auth.verify(parts[1]):
        resp = _error_response(401, "Unauthorized", "Invalid token")
        resp.headers["WWW-Authenticate"] = 'Bearer realm="admin"'
        return _add_cors(resp)

    return None


def _after_cors(request: Request, response: Response) -> None:
    """Add CORS headers to all routed responses."""
    _add_cors(response)


def _handle_404(request: Request, exc: HTTPException) -> Response:
    """Handle 404 errors with CORS headers."""
    return _add_cors(
        _error_response(404, "Not Found", f"Path not found: {request.path}")
    )


def _handle_405(request: Request, exc: HTTPException) -> Response:
    """Handle 405 errors with CORS headers."""
    return _add_cors(_error_response(405, "Method Not Allowed", "Method Not Allowed"))


# ============== Route Handlers ==============


def _handle_root(request: Request) -> Response:
    """Serve UI or API documentation."""
    if _app(request).serve_ui:
        return Response(
            body=ADMIN_HTML,
            status_code=200,
            content_type="text/html; charset=utf-8",
        )
    return _json_response(
        {
            "name": "ToolRegistry Admin API",
            "version": "1.0.0",
            "endpoints": [
                "GET /api/tools",
                "GET /api/tools/{name}",
                "POST /api/tools/{name}/enable",
                "POST /api/tools/{name}/disable",
                "PATCH /api/tools/{name}/metadata",
                "GET /api/namespaces",
                "POST /api/namespaces/{ns}/enable",
                "POST /api/namespaces/{ns}/disable",
                "PATCH /api/namespaces/{ns}/metadata",
                "GET /api/sources",
                "GET /api/logs",
                "GET /api/logs/stats",
                "DELETE /api/logs",
                "GET /api/state",
                "POST /api/state",
                "GET /api/permissions",
                "GET /api/config",
                "PUT /api/config",
            ],
        }
    )


def _get_tools(request: Request) -> Response:
    """Get all tools status."""
    registry = _app(request).registry
    tools_status = registry.get_tools_status()
    for tool_status in tools_status:
        tool_status["permission"] = _evaluate_tool_permission(
            registry, tool_status["name"]
        )
    return _json_response({"tools": tools_status})


def _get_tool(request: Request, name: str) -> Response:
    """Get single tool details."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    tool = registry.get_tool(name)
    if tool is None:
        return _error_response(404, "Not Found", f"Tool not found: {name}")

    enabled = registry.is_enabled(name)
    reason = registry.get_disable_reason(name) if not enabled else None

    tool_info = {
        "name": tool.name,
        "namespace": tool.namespace,
        "method_name": tool.method_name,
        "description": tool.description,
        "enabled": enabled,
        "reason": reason,
        "schema": tool.get_schema(),
        "permission": _evaluate_tool_permission(registry, name),
        "metadata": {
            "is_async": tool.metadata.is_async,
            "is_concurrency_safe": tool.metadata.is_concurrency_safe,
            "timeout": tool.metadata.timeout,
            "locality": tool.metadata.locality,
            "max_result_size": tool.metadata.max_result_size,
            "tags": sorted(str(t) for t in tool.metadata.tags),
            "custom_tags": sorted(tool.metadata.custom_tags),
            "source": tool.metadata.source,
            "source_detail": tool.metadata.source_detail,
            "defer": tool.metadata.defer,
            "search_hint": tool.metadata.search_hint,
            "think_augment": tool.metadata.think_augment,
            "extra": tool.metadata.extra,
        },
    }
    return _json_response(tool_info)


def _enable_tool(request: Request, name: str) -> Response:
    """Enable a tool."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    if name not in registry:
        return _error_response(404, "Not Found", f"Tool not found: {name}")

    registry.enable(name)
    return _json_response({"success": True, "message": f"Tool '{name}' enabled"})


def _disable_tool(request: Request, name: str) -> Response:
    """Disable a tool."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    if name not in registry:
        return _error_response(404, "Not Found", f"Tool not found: {name}")

    reason = ""
    if request.body:
        try:
            data = request.json()
            reason = data.get("reason", "")
        except (json.JSONDecodeError, ValueError):
            pass

    registry.disable(name, reason)
    return _json_response(
        {
            "success": True,
            "message": f"Tool '{name}' disabled",
            "reason": reason,
        }
    )


def _update_tool_metadata(request: Request, name: str) -> Response:
    """Update tool metadata."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)

    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")

    try:
        data = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")

    if not isinstance(data, dict) or not data:
        return _error_response(
            400, "Bad Request", "Body must be a non-empty JSON object"
        )

    try:
        registry.update_tool_metadata(name, **data)
    except KeyError:
        return _error_response(404, "Not Found", f"Tool not found: {name}")
    except ValueError as e:
        return _error_response(400, "Bad Request", str(e))

    return _json_response(
        {
            "success": True,
            "message": f"Metadata updated for tool '{name}'",
            "updated": data,
        }
    )


def _get_namespaces(request: Request) -> Response:
    """Get all namespaces."""
    registry = _app(request).registry
    namespaces: dict[str, dict[str, Any]] = {}
    for tool_name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(tool_name)
        if tool:
            ns = tool.namespace or "default"
            if ns not in namespaces:
                namespaces[ns] = {
                    "name": ns,
                    "tool_count": 0,
                    "enabled_count": 0,
                    "disabled_count": 0,
                    "async_count": 0,
                    "remote_count": 0,
                    "tags": set(),
                }
            namespaces[ns]["tool_count"] += 1
            if registry.is_enabled(tool_name):
                namespaces[ns]["enabled_count"] += 1
            else:
                namespaces[ns]["disabled_count"] += 1
            if tool.metadata.is_async:
                namespaces[ns]["async_count"] += 1
            if tool.metadata.locality == "remote":
                namespaces[ns]["remote_count"] += 1
            namespaces[ns]["tags"].update(tool.metadata.all_tags)

    for ns_data in namespaces.values():
        ns_data["tags"] = sorted(ns_data["tags"])

    result = sorted(
        namespaces.values(),
        key=lambda x: "" if x["name"] == "default" else x["name"],
    )
    return _json_response({"namespaces": result})


def _enable_namespace(request: Request, name: str) -> Response:
    """Enable all tools in namespace."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    registry.enable(name)

    enabled_count = 0
    for tool_name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(tool_name)
        if tool and tool.namespace == name:
            registry.enable(tool_name)
            enabled_count += 1

    return _json_response(
        {
            "success": True,
            "message": f"Namespace '{name}' enabled",
            "tools_enabled": enabled_count,
        }
    )


def _disable_namespace(request: Request, name: str) -> Response:
    """Disable all tools in namespace."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)

    reason = ""
    if request.body:
        try:
            data = request.json()
            reason = data.get("reason", "")
        except (json.JSONDecodeError, ValueError):
            pass

    registry.disable(name, reason)

    affected_count = 0
    for tool_name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(tool_name)
        if tool and tool.namespace == name:
            affected_count += 1

    return _json_response(
        {
            "success": True,
            "message": f"Namespace '{name}' disabled",
            "tools_affected": affected_count,
            "reason": reason,
        }
    )


def _update_namespace_metadata(request: Request, name: str) -> Response:
    """Update namespace metadata."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)

    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")

    try:
        data = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")

    if not isinstance(data, dict) or not data:
        return _error_response(
            400, "Bad Request", "Body must be a non-empty JSON object"
        )

    try:
        registry.update_namespace_metadata(name, **data)
    except KeyError:
        return _error_response(404, "Not Found", f"Namespace not found: {name}")
    except ValueError as e:
        return _error_response(400, "Bad Request", str(e))

    tools_updated = sum(
        1
        for tn in registry.list_tools(include_disabled=True)
        if (t := registry.get_tool(tn)) and t.namespace == name
    )

    return _json_response(
        {
            "success": True,
            "message": f"Metadata updated for namespace '{name}'",
            "tools_updated": tools_updated,
            "updated": data,
        }
    )


def _get_logs(request: Request) -> Response:
    """Get execution logs."""
    registry = _app(request).registry
    log = registry.get_execution_log()
    if log is None:
        return _error_response(
            400, "Logging Disabled", "Execution logging is not enabled"
        )

    limit = int(request.query_params.get("limit", ["100"])[0])
    tool_name = request.query_params.get("tool_name", [None])[0]
    status_str = request.query_params.get("status", [None])[0]

    from .execution_log import ExecutionStatus

    status = None
    if status_str:
        try:
            status = ExecutionStatus(status_str)
        except ValueError:
            pass

    entries = log.get_entries(limit=limit, tool_name=tool_name, status=status)
    entries_data = [asdict(entry) for entry in entries]

    return _json_response({"entries": entries_data, "count": len(entries_data)})


def _get_log_stats(request: Request) -> Response:
    """Get execution statistics."""
    registry = _app(request).registry
    log = registry.get_execution_log()
    if log is None:
        return _error_response(
            400, "Logging Disabled", "Execution logging is not enabled"
        )

    stats = log.get_stats()
    return _json_response(stats)


def _clear_logs(request: Request) -> Response:
    """Clear execution logs."""
    registry = _app(request).registry
    log = registry.get_execution_log()
    if log is None:
        return _error_response(
            400, "Logging Disabled", "Execution logging is not enabled"
        )

    cleared = log.clear()
    return _json_response(
        {"success": True, "message": f"Cleared {cleared} log entries"}
    )


def _get_sources(request: Request) -> Response:
    """Get aggregated tool sources."""
    registry = _app(request).registry
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}

    for tool_name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(tool_name)
        if tool is None:
            continue
        meta = tool.metadata
        ns = tool.namespace or "default"
        key = (meta.source, meta.source_detail, ns)

        if key not in groups:
            groups[key] = {
                "type": meta.source,
                "detail": meta.source_detail,
                "namespace": ns,
                "tool_count": 0,
                "enabled_count": 0,
                "tools": [],
            }
        groups[key]["tool_count"] += 1
        if registry.is_enabled(tool_name):
            groups[key]["enabled_count"] += 1
        groups[key]["tools"].append(tool_name)

    sources = sorted(groups.values(), key=lambda s: (s["type"], s["namespace"]))
    return _json_response({"sources": sources})


def _export_state(request: Request) -> Response:
    """Export current state including source metadata."""
    registry = _app(request).registry
    sources: dict[str, dict[str, str]] = {}
    for tool_name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(tool_name)
        if tool:
            sources[tool_name] = {
                "source": tool.metadata.source,
                "source_detail": tool.metadata.source_detail,
            }
    state = {
        "disabled": dict(registry._disabled),
        "tools": registry.list_tools(include_disabled=True),
        "sources": sources,
    }
    return _json_response(state)


def _import_state(request: Request) -> Response:
    """Import/restore state."""
    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")

    try:
        state = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")

    registry = _app(request).registry
    if "disabled" in state:
        registry._disabled.clear()
        for n, reason in state["disabled"].items():
            registry.disable(n, reason)

    return _json_response({"success": True, "message": "State restored successfully"})


def _get_permissions(request: Request) -> Response:
    """Get permission policy info."""
    registry = _app(request).registry
    policy = registry.get_permission_policy()
    handler = registry.get_permission_handler()

    if policy is None:
        return _json_response(
            {
                "has_policy": False,
                "fallback": registry.permission_fallback.value,
                "has_handler": handler is not None,
                "rules": [],
            }
        )

    rules = [
        {
            "name": rule.name,
            "result": rule.result.value,
            "reason": rule.reason,
        }
        for rule in policy.rules
    ]

    return _json_response(
        {
            "has_policy": True,
            "fallback": policy.fallback.value,
            "has_handler": policy.handler is not None or handler is not None,
            "rules": rules,
        }
    )


def _get_config(request: Request) -> Response:
    """Get the current tool configuration."""
    config = _app(request).config
    if config is None:
        return _error_response(404, "Not Found", "No tool configuration is loaded")
    data = config.to_dict()
    data["source"] = config.source
    return _json_response(data)


def _update_config(request: Request) -> Response:
    """Update tool configuration and persist to disk."""
    from dataclasses import replace

    from ..config import save_config

    app = _app(request)
    config = app.config
    if config is None:
        return _error_response(404, "Not Found", "No tool configuration is loaded")

    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")

    try:
        data = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return _error_response(400, "Bad Request", "Body must be a JSON object")

    # Build kwargs for replace()
    updates: dict[str, Any] = {}
    if "mode" in data:
        mode = data["mode"]
        if mode not in ("denylist", "allowlist"):
            return _error_response(
                400,
                "Bad Request",
                f"Invalid mode '{mode}'. Must be 'denylist' or 'allowlist'.",
            )
        updates["mode"] = mode
    if "disabled" in data:
        if not isinstance(data["disabled"], list):
            return _error_response(400, "Bad Request", "'disabled' must be a list")
        updates["disabled"] = tuple(data["disabled"])
    if "enabled" in data:
        if not isinstance(data["enabled"], list):
            return _error_response(400, "Bad Request", "'enabled' must be a list")
        updates["enabled"] = tuple(data["enabled"])

    if not updates:
        return _error_response(
            400,
            "Bad Request",
            "No valid fields to update. Supported: mode, disabled, enabled.",
        )

    new_config = replace(config, **updates)

    # Persist to disk if source path is known
    saved_path = ""
    if config.source:
        try:
            save_config(new_config, config.source)
            new_config = replace(new_config, source=config.source)
            saved_path = config.source
        except Exception as e:
            return _error_response(
                500, "Internal Server Error", f"Failed to write config file: {e}"
            )

    app.config = new_config

    result = new_config.to_dict()
    result["source"] = new_config.source
    result["saved"] = bool(saved_path)
    if saved_path:
        result["saved_path"] = saved_path
    return _json_response(result)


# ============== Route Setup ==============


def setup_routes(app: "AdminApp") -> None:
    """Register all middleware and routes on the app.

    Args:
        app: The AdminApp instance with ``registry``, ``auth``,
            and ``serve_ui`` attributes.
    """
    # Middleware
    app.before_request(_cors_preflight)
    app.before_request(_auth_check)
    app.after_request(_after_cors)
    app.errorhandler(404)(_handle_404)
    app.errorhandler(405)(_handle_405)

    # Routes
    app.get("/")(_handle_root)
    app.get("/api/tools")(_get_tools)
    app.get("/api/tools/<name>")(_get_tool)
    app.post("/api/tools/<name>/enable")(_enable_tool)
    app.post("/api/tools/<name>/disable")(_disable_tool)
    app.patch("/api/tools/<name>/metadata")(_update_tool_metadata)
    app.get("/api/namespaces")(_get_namespaces)
    app.post("/api/namespaces/<name>/enable")(_enable_namespace)
    app.post("/api/namespaces/<name>/disable")(_disable_namespace)
    app.patch("/api/namespaces/<name>/metadata")(_update_namespace_metadata)
    app.get("/api/sources")(_get_sources)
    app.get("/api/logs")(_get_logs)
    app.get("/api/logs/stats")(_get_log_stats)
    app.delete("/api/logs")(_clear_logs)
    app.get("/api/state")(_export_state)
    app.post("/api/state")(_import_state)
    app.get("/api/permissions")(_get_permissions)
    app.get("/api/config")(_get_config)
    app.put("/api/config")(_update_config)
