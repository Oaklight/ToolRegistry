"""HTTP request handlers for admin panel.

This module provides route registration for the admin panel using
the zerodep httpserver, implementing REST API endpoints for tool
management and monitoring.
"""

import json
import os
import urllib.parse
from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from .._vendor.httpserver import HTTPException, Request, Response
from ..utils import ToolResultJSONEncoder

from .static import read_asset, read_shell

if TYPE_CHECKING:
    from toolregistry import ToolRegistry

    from .server import AdminApp


# ============== CORS Constants ==============

_CORS_HEADERS = {
    "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}
"""Headers shared by every response.

``Access-Control-Allow-Origin`` is deliberately absent: it is added per
request only for same-origin callers.  The panel is commonly served on
localhost without authentication, and a wildcard let any website read tool
metadata and toggle tools through the user's browser.
"""

_SECURITY_HEADERS = {
    # The UI shell is served without a token so its own prompt can run.  A
    # frame loads that shell with the origin's localStorage, so without frame
    # protection any page could embed a fully authenticated panel and
    # clickjack its destructive controls.
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
}
"""Frame protections applied to every admin response."""


# ============== Request Helpers ==============


def _app(request: Request) -> "AdminApp":
    """Get the typed AdminApp from a request."""
    from .server import AdminApp

    return cast(AdminApp, request.app)


# ============== Response Helpers ==============


def _json_response(data: Any, status_code: int = 200) -> Response:
    """Create a JSON response.

    Values a tool may produce -- ``datetime``, ``Decimal``, ``set``,
    dataclasses, non-finite floats -- are projected by
    :class:`ToolResultJSONEncoder`, so a ``NaN`` becomes ``null`` rather than
    the bare constant, which is not valid JSON and would make the whole body
    unparseable in the browser.  ``allow_nan=False`` keeps that a hard
    failure if a value ever reaches ``json`` without going through the
    encoder.

    Args:
        data: The data to serialize as JSON.
        status_code: HTTP status code.

    Returns:
        Response with JSON content type.
    """
    body = json.dumps(data, cls=ToolResultJSONEncoder, allow_nan=False)
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


def _same_origin(request: Request) -> str | None:
    """Return the request Origin when it points at this server.

    Compares the Origin's netloc with the Host header, which covers the
    browser's same-origin requests and reverse-proxy deployments where the
    proxy preserves Host.
    """
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")
    if not origin or not host:
        return None
    parts = urllib.parse.urlsplit(origin)
    if parts.scheme in ("http", "https") and parts.netloc == host:
        return origin
    return None


def _add_cors(request: Request, response: Response) -> Response:
    """Add CORS headers to a response.

    Cross-origin browser access is denied by default; only a same-origin
    caller receives ``Access-Control-Allow-Origin``.  See ``_CORS_HEADERS``.

    Args:
        request: The incoming request, used to check the Origin.
        response: The response to add headers to.

    Returns:
        The response with CORS headers added.
    """
    response.headers.update(_CORS_HEADERS)
    response.headers.update(_SECURITY_HEADERS)
    # Set on every response, not only when an origin is echoed: a cache that
    # normalises or strips Vary must never mix the two shapes.
    response.headers.setdefault("Vary", "Origin")
    origin = _same_origin(request)
    if origin is not None:
        response.headers["Access-Control-Allow-Origin"] = origin
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
        return _add_cors(request, Response(status_code=204))
    return None


def _auth_check(request: Request) -> Response | None:
    """Check authentication via Bearer token or session cookie.

    When an ``Authorization`` header is present, it **must** be a valid
    Bearer token — a malformed or invalid header is always rejected even
    if a valid session cookie is also present (explicit auth header
    signals explicit intent).  Cookie fallback only applies when no
    ``Authorization`` header is sent at all.
    """
    app = _app(request)
    auth = app.auth
    if auth is None:
        return None

    # The UI shell must load before the token prompt can run: a browser cannot
    # attach an Authorization header to a top-level navigation.  The shell is a
    # static document with no registry data, and every /api request below still
    # requires credentials.  When the UI is disabled, "/" is an API index and
    # stays protected.  HEAD mirrors GET (the server strips the body) so a
    # health check agrees with a browser.
    if request.method in ("GET", "HEAD") and request.path == "/" and app.serve_ui:
        return None

    # The shell is useless without its stylesheets and scripts, and the browser
    # requests them without credentials.  ``read_asset`` serves only the css/
    # and js/ files shipped in the package, so this exposes no registry data.
    if (
        request.method in ("GET", "HEAD")
        and request.path.startswith("/assets/")
        and app.serve_ui
    ):
        return None

    session = app.session
    auth_header = request.headers.get("authorization", "")

    # Try Bearer token first
    if auth_header:
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            resp = _error_response(401, "Unauthorized", "Invalid Authorization format")
            resp.headers["WWW-Authenticate"] = 'Bearer realm="admin"'
            return _add_cors(request, resp)
        if not auth.verify(parts[1]):
            resp = _error_response(401, "Unauthorized", "Invalid token")
            resp.headers["WWW-Authenticate"] = 'Bearer realm="admin"'
            return _add_cors(request, resp)
        setattr(request.state, "set_session_cookie", True)
        return None

    # Fall back to session cookie (sliding window — reissue on each use)
    if session is not None:
        cookie_val = request.cookies.get(session.cookie_name, "")
        if cookie_val and session.verify(cookie_val):
            setattr(request.state, "set_session_cookie", True)
            return None

    resp = _error_response(401, "Unauthorized", "Missing credentials")
    resp.headers["WWW-Authenticate"] = 'Bearer realm="admin"'
    return _add_cors(request, resp)


def _set_session_cookie(request: Request, response: Response) -> None:
    """Set a session cookie after successful Bearer authentication."""
    if not getattr(request.state, "set_session_cookie", False):
        return
    session = _app(request).session
    if session is None:
        return
    token = session.issue()
    # Secure omitted — admin panel often runs on localhost (plain HTTP).
    # Add secure=True when serving behind TLS.
    response.set_cookie(
        session.cookie_name,
        token,
        max_age=session.max_age,
        httponly=True,
        samesite="Lax",
        path="/",
    )


def _after_cors(request: Request, response: Response) -> None:
    """Add CORS headers to all routed responses."""
    _add_cors(request, response)


def _handle_404(request: Request, exc: HTTPException) -> Response:
    """Handle 404 errors with CORS headers."""
    return _add_cors(
        request, _error_response(404, "Not Found", f"Path not found: {request.path}")
    )


def _handle_405(request: Request, exc: HTTPException) -> Response:
    """Handle 405 errors with CORS headers."""
    return _add_cors(
        request, _error_response(405, "Method Not Allowed", "Method Not Allowed")
    )


# ============== Route Handlers ==============


def _handle_root(request: Request) -> Response:
    """Serve UI or API documentation."""
    if _app(request).serve_ui:
        return Response(
            body=read_shell(),
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
                "GET /api/metrics",
                "GET /api/state",
                "POST /api/state",
                "GET /api/permissions",
                "GET /api/config",
                "PUT /api/config",
            ],
        }
    )


def _serve_asset(request: Request, name: str) -> Response:
    """Serve one shipped stylesheet or script from ``/assets/<name>``."""
    if not _app(request).serve_ui:
        raise HTTPException(404, "Not Found")
    asset = read_asset(name)
    if asset is None:
        raise HTTPException(404, "Not Found")
    body, content_type = asset
    return Response(
        body=body,
        status_code=200,
        content_type=content_type,
        headers={"Cache-Control": "no-cache"},
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
            "title": tool.metadata.title,
            "think_augment": tool.metadata.think_augment,
            "execution_hints": tool.metadata.execution_hints,
            "extra": tool.metadata.extra,
        },
    }
    return _json_response(tool_info)


def _check_env_requirements(
    registry: "ToolRegistry", name: str
) -> tuple[bool, list[str]]:
    """Check if missing-env requirements are now satisfied.

    Inspects the disable reason for a ``"Missing env: ..."`` prefix and
    verifies whether the listed environment variables are now set.

    Args:
        registry: The ToolRegistry instance.
        name: Tool or namespace name.

    Returns:
        A tuple of ``(satisfied, missing_vars)``.
    """
    reason = registry.get_disable_reason(name)
    if not reason or not reason.startswith("Missing env:"):
        return True, []
    env_str = reason[len("Missing env:") :].strip()
    env_vars = [v.strip() for v in env_str.split(",") if v.strip()]
    missing = [v for v in env_vars if not os.environ.get(v)]
    return len(missing) == 0, missing


def _enable_tool(request: Request, name: str) -> Response:
    """Enable a tool."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    if name not in registry:
        return _error_response(404, "Not Found", f"Tool not found: {name}")

    satisfied, missing = _check_env_requirements(registry, name)
    if not satisfied:
        return _error_response(
            400,
            "Bad Request",
            f"Cannot enable '{name}': missing env vars: {', '.join(missing)}",
        )

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
    """Update tool metadata, persisting search_hint/defer to config if loaded."""
    app = _app(request)
    registry = app.registry
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

    # Persist whitelisted metadata fields to the config file when one is
    # loaded.  Reuse the previous override (when present) so fields absent
    # from this request are preserved instead of silently dropped.
    saved = False
    persist_fields = {
        "search_hint",
        "defer",
        "title",
        "read_only_hint",
        "destructive_hint",
        "idempotent_hint",
        "open_world_hint",
    }
    if persist_fields & set(data):
        config = app.config
        if config is not None and config.source:
            from dataclasses import replace

            from ..config import ToolMetadataOverride, save_config

            existing = dict(config.tool_metadata)
            prev = existing.get(name)
            updates = {field: data[field] for field in persist_fields if field in data}
            new_override = (
                replace(prev, **updates)
                if prev is not None
                else ToolMetadataOverride(**updates)
            )
            existing[name] = new_override
            new_config = replace(config, tool_metadata=existing)
            try:
                save_config(new_config, config.source)
                app.config = new_config
                saved = True
            except Exception:
                pass  # persist is best-effort; in-memory update already done

    return _json_response(
        {
            "success": True,
            "message": f"Metadata updated for tool '{name}'",
            "updated": data,
            "saved": saved,
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

    # Check env requirements on any tool in the namespace
    skipped: list[str] = []
    enabled_count = 0
    for tool_name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(tool_name)
        if tool and tool.namespace == name:
            satisfied, missing = _check_env_requirements(registry, tool_name)
            if not satisfied:
                skipped.extend(missing)
            else:
                registry.enable(tool_name)
                enabled_count += 1

    if skipped and enabled_count == 0:
        # All tools blocked by missing env vars
        unique_missing = sorted(set(skipped))
        return _error_response(
            400,
            "Bad Request",
            f"Cannot enable namespace '{name}': "
            f"missing env vars: {', '.join(unique_missing)}",
        )

    # Enable at namespace level too (removes namespace-level disable)
    registry.enable(name)

    result: dict[str, Any] = {
        "success": True,
        "message": f"Namespace '{name}' enabled",
        "tools_enabled": enabled_count,
    }
    if skipped:
        result["skipped_missing_env"] = sorted(set(skipped))
    return _json_response(result)


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
    has_warnings_str = request.query_params.get("has_warnings", [None])[0]

    from .execution_log import ExecutionStatus

    status = None
    if status_str:
        try:
            status = ExecutionStatus(status_str)
        except ValueError:
            pass

    has_warnings: bool | None = None
    if has_warnings_str is not None:
        has_warnings = has_warnings_str.lower() in ("true", "1", "yes")

    entries = log.get_entries(
        limit=limit, tool_name=tool_name, status=status, has_warnings=has_warnings
    )
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


def _get_metrics(request: Request) -> Response:
    """Get HTTP request metrics for the admin server."""
    metrics = _app(request).metrics
    if metrics is None:
        return _error_response(
            503, "Metrics Unavailable", "Request metrics are not initialized"
        )
    return _json_response(metrics.snapshot())


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
    """Import/restore state.

    The payload is validated in full before the registry is touched so a
    malformed import can never clear the existing disabled set.  Import is a
    wholesale replacement, so every name must resolve to a registered tool or
    namespace: a state file from another registry (or a single typo) would
    otherwise re-enable the current tools and disable nothing real.
    """
    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")

    try:
        state = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")

    if not isinstance(state, dict):
        return _error_response(400, "Bad Request", "Body must be a JSON object")

    registry = _app(request).registry
    if "disabled" not in state:
        return _json_response(
            {"success": True, "message": "State restored successfully"}
        )

    disabled = state["disabled"]
    if not isinstance(disabled, dict):
        return _error_response(
            400,
            "Bad Request",
            "'disabled' must be an object mapping tool names to reasons",
        )

    clean: dict[str, str] = {}
    for name, reason in disabled.items():
        if not isinstance(name, str) or not isinstance(reason, str):
            return _error_response(
                400, "Bad Request", "'disabled' keys and values must be strings"
            )
        clean[name] = reason

    known_tools = set(registry.list_tools(include_disabled=True))
    known_namespaces: set[str] = set()
    for tool_name in known_tools:
        tool = registry.get_tool(tool_name)
        if tool is not None and tool.namespace:
            known_namespaces.add(tool.namespace)

    unknown = sorted(
        name
        for name in clean
        if name not in known_tools and name not in known_namespaces
    )
    if unknown:
        return _error_response(
            400,
            "Bad Request",
            "Unknown tool or namespace: " + ", ".join(unknown),
        )

    registry._disabled.clear()
    for name, reason in clean.items():
        registry.disable(name, reason)

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


def _validate_config_field(
    data: dict, field: str, updates: dict[str, Any]
) -> Response | None:
    """Validate a single config update field and add it to updates.

    Returns:
        An error Response if validation fails, None on success.
    """
    if field not in data:
        return None
    if field == "mode":
        mode = data["mode"]
        if mode not in ("denylist", "allowlist"):
            return _error_response(
                400,
                "Bad Request",
                f"Invalid mode '{mode}'. Must be 'denylist' or 'allowlist'.",
            )
        updates["mode"] = mode
    else:  # "disabled" or "enabled"
        if not isinstance(data[field], list):
            return _error_response(400, "Bad Request", f"'{field}' must be a list")
        updates[field] = tuple(data[field])
    return None


def _update_config(request: Request) -> Response:
    """Update tool configuration and persist to disk."""
    from dataclasses import replace

    from ..config import save_config

    app = _app(request)

    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")

    try:
        data = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        return _error_response(400, "Bad Request", "Body must be a JSON object")

    # name_sep — applies to the registry directly (not to the config file)
    # Allow this even when no config file is loaded.  The setter owns the
    # validation, so the accepted values are defined in one place.
    if "name_sep" in data:
        try:
            app.registry.name_sep = data["name_sep"]
        except (TypeError, ValueError) as exc:
            return _error_response(400, "Bad Request", str(exc))

    updates: dict[str, Any] = {}
    for field in ("mode", "disabled", "enabled"):
        err = _validate_config_field(data, field, updates)
        if err is not None:
            return err

    if not updates:
        if "name_sep" not in data:
            return _error_response(
                400,
                "Bad Request",
                "No valid fields to update. Supported: mode, disabled, enabled, name_sep.",
            )
        # name_sep-only update: return current info
        return _json_response({"name_sep": data["name_sep"], "saved": False})

    config = app.config
    if config is None:
        return _error_response(404, "Not Found", "No tool configuration is loaded")

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


# ============== Version Info ==============


def _get_info(request: Request) -> Response:
    """Return version information for toolregistry and optional dependencies."""
    import toolregistry

    registry = _app(request).registry
    info: dict[str, Any] = {
        "toolregistry": toolregistry.__version__,
        "name_sep": registry.name_sep,
        "discover_enabled": "discover_tools" in registry._tools
        and registry.is_enabled("discover_tools"),
    }
    try:
        import toolregistry_server

        info["toolregistry_server"] = toolregistry_server.__version__
    except ImportError:
        pass
    try:
        import toolregistry_hub

        info["toolregistry_hub"] = toolregistry_hub.__version__
    except ImportError:
        pass
    return _json_response(info)


# ============== Aggregate Schema ==============


def _schema_counts(registry: "ToolRegistry") -> tuple[int, int]:
    """Return (deferred_count, disabled_count) for the registry.

    Args:
        registry: The tool registry to inspect.

    Returns:
        A tuple of (deferred_count, disabled_count).
    """
    deferred_count = sum(
        1
        for name, tool in registry._tools.items()
        if registry.is_enabled(name)
        and getattr(getattr(tool, "metadata", None), "defer", False)
    )
    disabled_count = sum(1 for name in registry._tools if not registry.is_enabled(name))
    return deferred_count, disabled_count


def _get_schema(request: Request) -> Response:
    """Return the aggregate tool schema or the discover_tools description.

    Query parameters:
        format: One of ``openai-chat`` (default), ``openai-response``,
            ``anthropic``, ``gemini``, or ``discover``.  When ``discover``
            is specified, the raw ``discover_tools`` description text is
            returned instead of a schema list.

    Returns:
        JSON with ``format``, ``count``, ``deferred_count``,
        ``disabled_count``, and either ``schema`` (list) or ``text`` (str).
    """
    registry = _app(request).registry
    fmt_str = request.query_params.get("format", ["openai-chat"])[0]

    # --- discover_tools description view ---
    if fmt_str == "discover":
        discovery_tool = registry._tools.get("discover_tools")
        if discovery_tool is None or not registry.is_enabled("discover_tools"):
            return _error_response(404, "Not Found", "Tool discovery is not enabled")
        deferred_count, disabled_count = _schema_counts(registry)

        _hint_threshold = 80

        def _first_sentence(text: str) -> str:
            line = text.split("\n")[0].strip()
            dot = line.find(". ")
            return line[: dot + 1] if dot != -1 else line

        tools_list = [
            {
                "name": t_name,
                "description": _first_sentence(tool.description or ""),
                "has_search_hint": bool(
                    getattr(getattr(tool, "metadata", None), "search_hint", "")
                ),
                "long": len(_first_sentence(tool.description or "")) > _hint_threshold,
            }
            for t_name, tool in registry._tools.items()
            if t_name != "discover_tools"
            and registry.is_enabled(t_name)
            and getattr(getattr(tool, "metadata", None), "defer", False)
        ]

        return _json_response(
            {
                "format": "discover",
                "count": deferred_count,
                "deferred_count": deferred_count,
                "disabled_count": disabled_count,
                "text": discovery_tool.description or "",
                "tools": tools_list,
            }
        )

    # --- LLM schema formats ---
    from ..llm.tool_calls import API_FORMATS

    valid = {
        "openai-chat",
        "openai-responses",
        "anthropic",
        "gemini",
        "google-interactions",
        "rosetta-ir",
        # Canonical names, accepted so the panel and the API speak the same
        # vocabulary; _normalize_api_format maps them internally.
        "chat_completions",
        "open_responses",
        "messages",
        "google_generate",
        "google_interactions",
        "rosetta_ir",
    }
    if fmt_str not in valid:
        return _error_response(
            400,
            "Bad Request",
            f"Invalid format '{fmt_str}'. Must be one of: {', '.join(sorted(valid | {'discover'}))}",
        )
    fmt = cast(API_FORMATS, fmt_str)
    schemas = registry.get_schemas(api_format=fmt, include_deferred=False)
    deferred_count, disabled_count = _schema_counts(registry)
    return _json_response(
        {
            "format": fmt_str,
            "count": len(schemas),
            "deferred_count": deferred_count,
            "disabled_count": disabled_count,
            "schema": schemas,
        }
    )


# ============== Route Setup ==============


def _source_body(request: Request) -> dict[str, Any] | Response:
    """Parse a source request body, or return the error response."""
    if not request.body:
        return _error_response(400, "Bad Request", "Request body is required")
    try:
        data = request.json()
    except (json.JSONDecodeError, ValueError) as e:
        return _error_response(400, "Bad Request", f"Invalid JSON: {e}")
    if not isinstance(data, dict):
        return _error_response(400, "Bad Request", "Body must be a JSON object")
    return data


def _preview_source(request: Request) -> Response:
    """List the tools a source offers without registering any of them."""
    from .registration import SourceError, preview_source

    data = _source_body(request)
    if isinstance(data, Response):
        return data
    kind = data.get("kind")
    if not isinstance(kind, str):
        return _error_response(400, "Bad Request", "'kind' is required")

    try:
        result = preview_source(_app(request).registry, kind, data)
    except SourceError as e:
        return _error_response(400, "Bad Request", str(e))
    return _json_response(result)


def _register_source(request: Request) -> Response:
    """Register the selected tools of a source."""
    from .registration import SourceError, register_tools

    data = _source_body(request)
    if isinstance(data, Response):
        return data
    kind = data.get("kind")
    if not isinstance(kind, str):
        return _error_response(400, "Bad Request", "'kind' is required")

    try:
        result = register_tools(_app(request).registry, kind, data)
    except SourceError as e:
        return _error_response(400, "Bad Request", str(e))
    return _json_response(result)


def _override_summary(tool: Any) -> dict[str, Any]:
    """Return the fields an override can change, for display and diffing."""
    metadata = tool.metadata
    return {
        "name": tool.name,
        "description": tool.description,
        "namespace": tool.namespace,
        "tags": sorted(getattr(tag, "value", str(tag)) for tag in metadata.tags),
        "custom_tags": sorted(metadata.custom_tags),
        "title": getattr(metadata, "title", ""),
        "read_only_hint": metadata.read_only_hint,
        "destructive_hint": metadata.destructive_hint,
        "idempotent_hint": metadata.idempotent_hint,
        "open_world_hint": metadata.open_world_hint,
    }


def _list_overrides(request: Request) -> Response:
    """List overridden tools with their current and original definitions."""
    registry = _app(request).registry
    entries = []
    for name in sorted(registry.list_overrides()):
        current = registry.get_tool(name)
        original = (
            registry._overrides.get(name) if hasattr(registry, "_overrides") else None
        )
        if current is None:
            continue
        entries.append(
            {
                "name": name,
                "current": _override_summary(current),
                "original": _override_summary(original)
                if original is not None
                else None,
            }
        )
    return _json_response({"overrides": entries, "count": len(entries)})


_OVERRIDE_METADATA_FIELDS = (
    "title",
    "read_only_hint",
    "destructive_hint",
    "idempotent_hint",
    "open_world_hint",
)


def _override_tool(request: Request, name: str) -> Response:
    """Override a tool's description, tags or hints, recording the original."""
    from dataclasses import replace

    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    tool = registry.get_tool(name)
    if tool is None:
        return _error_response(404, "Not Found", f"Tool not found: {name}")

    data = _source_body(request)
    if isinstance(data, Response):
        return data

    # Validate everything before touching the registry: a rejected field must
    # not leave the tool half-overridden.
    unknown = sorted(
        set(data)
        - {"description", "tags", "custom_tags"}
        - set(_OVERRIDE_METADATA_FIELDS)
    )
    if unknown:
        return _error_response(
            400, "Bad Request", "Unknown override field(s): " + ", ".join(unknown)
        )

    description = data.get("description", tool.description)
    if not isinstance(description, str):
        return _error_response(400, "Bad Request", "'description' must be a string")

    from ..tool import ToolTag

    tags = tool.metadata.tags
    if "tags" in data:
        raw_tags = data["tags"]
        if not isinstance(raw_tags, list) or not all(
            isinstance(t, str) for t in raw_tags
        ):
            return _error_response(
                400, "Bad Request", "'tags' must be a list of strings"
            )
        try:
            tags = {ToolTag(value) for value in raw_tags}
        except ValueError as e:
            return _error_response(400, "Bad Request", f"Unknown tag: {e}")

    custom_tags = tool.metadata.custom_tags
    if "custom_tags" in data:
        raw_custom = data["custom_tags"]
        if not isinstance(raw_custom, list) or not all(
            isinstance(tag, str) for tag in raw_custom
        ):
            return _error_response(
                400, "Bad Request", "'custom_tags' must be a list of strings"
            )
        custom_tags = set(raw_custom)

    meta_updates: dict[str, Any] = {"tags": tags, "custom_tags": custom_tags}
    for field in _OVERRIDE_METADATA_FIELDS:
        if field in data:
            meta_updates[field] = data[field]

    new_metadata = replace(tool.metadata, **meta_updates)
    new_tool = replace(tool, description=description, metadata=new_metadata)
    registry.override(name, new_tool)

    original = (
        registry._overrides.get(name) if hasattr(registry, "_overrides") else None
    )
    return _json_response(
        {
            "success": True,
            "name": name,
            "current": _override_summary(registry.get_tool(name)),
            "original": _override_summary(original) if original is not None else None,
        }
    )


def _restore_tool_override(request: Request, name: str) -> Response:
    """Drop an override and restore the tool that was registered first."""
    registry = _app(request).registry
    name = urllib.parse.unquote(name)
    try:
        restored = registry.restore_override(name)
    except KeyError:
        return _error_response(404, "Not Found", f"No override recorded for: {name}")
    return _json_response(
        {"success": True, "name": name, "restored": _override_summary(restored)}
    )


def _deferred_tools(registry: Any) -> list[str]:
    """Names of tools marked deferred, in registry order."""
    names: list[str] = []
    for name in registry.list_tools(include_disabled=True):
        tool = registry.get_tool(name)
        if tool is not None and getattr(tool.metadata, "defer", False):
            names.append(name)
    return names


def _get_discovery(request: Request) -> Response:
    """Report whether tool discovery is enabled and what it would restore."""
    registry = _app(request).registry
    deferred = _deferred_tools(registry)
    return _json_response(
        {
            "enabled": bool(registry.tool_discovery_enabled),
            "deferred_count": len(deferred),
            "deferred_tools": deferred,
        }
    )


def _enable_tool_discovery(request: Request) -> Response:
    """Register ``discover_tools`` and ``call_deferred``.

    Enabling is safe to repeat: the registry keeps its existing discoverer
    and reports the options it was built with.
    """
    registry = _app(request).registry
    try:
        registry.enable_tool_discovery()
    except Exception as e:  # noqa: BLE001 - reported to the operator
        return _error_response(400, "Bad Request", str(e))
    return _json_response(
        {
            "success": True,
            "enabled": True,
            "registered": [
                name
                for name in ("discover_tools", "call_deferred")
                if name in registry.list_tools(include_disabled=True)
            ],
            "deferred_count": len(_deferred_tools(registry)),
        }
    )


def _disable_tool_discovery(request: Request) -> Response:
    """Unregister ``discover_tools`` and ``call_deferred``.

    Deferred tools stay registered but become unreachable to a model, so the
    response reports how many are in that state.
    """
    registry = _app(request).registry
    deferred = _deferred_tools(registry)
    registry.disable_tool_discovery()
    return _json_response(
        {
            "success": True,
            "enabled": False,
            "unreachable": len(deferred),
            "deferred_tools": deferred,
        }
    )


def setup_routes(app: "AdminApp") -> None:
    """Register all middleware and routes on the app.

    Args:
        app: The AdminApp instance with ``registry``, ``auth``,
            and ``serve_ui`` attributes.
    """
    # Middleware
    app.before_request(_cors_preflight)
    app.before_request(_auth_check)
    app.after_request(_set_session_cookie)
    app.after_request(_after_cors)
    app.errorhandler(404)(_handle_404)
    app.errorhandler(405)(_handle_405)

    # Routes
    app.get("/")(_handle_root)
    app.get("/assets/<path:name>")(_serve_asset)
    app.post("/api/sources/preview")(_preview_source)
    app.post("/api/sources/register")(_register_source)
    app.get("/api/overrides")(_list_overrides)
    app.get("/api/discovery")(_get_discovery)
    app.post("/api/discovery/enable")(_enable_tool_discovery)
    app.post("/api/discovery/disable")(_disable_tool_discovery)
    app.post("/api/tools/<path:name>/override")(_override_tool)
    app.delete("/api/tools/<path:name>/override")(_restore_tool_override)
    app.get("/api/tools")(_get_tools)
    app.get("/api/tools/<path:name>")(_get_tool)
    app.post("/api/tools/<path:name>/enable")(_enable_tool)
    app.post("/api/tools/<path:name>/disable")(_disable_tool)
    app.patch("/api/tools/<path:name>/metadata")(_update_tool_metadata)
    app.get("/api/namespaces")(_get_namespaces)
    app.post("/api/namespaces/<path:name>/enable")(_enable_namespace)
    app.post("/api/namespaces/<path:name>/disable")(_disable_namespace)
    app.patch("/api/namespaces/<path:name>/metadata")(_update_namespace_metadata)
    app.get("/api/sources")(_get_sources)
    app.get("/api/logs")(_get_logs)
    app.get("/api/logs/stats")(_get_log_stats)
    app.get("/api/metrics")(_get_metrics)
    app.delete("/api/logs")(_clear_logs)
    app.get("/api/state")(_export_state)
    app.post("/api/state")(_import_state)
    app.get("/api/permissions")(_get_permissions)
    app.get("/api/config")(_get_config)
    app.put("/api/config")(_update_config)
    app.get("/api/info")(_get_info)
    app.get("/api/schema")(_get_schema)
