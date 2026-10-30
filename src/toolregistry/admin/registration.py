"""Inspect and register tools from a source, on behalf of the admin panel.

The panel's Register section needs two things the library did not expose as
data: a list of the tools a *source* offers before anything is registered, and
a way to register only the ones the operator picked.  Both live here so the
HTTP layer stays a thin adapter and the behaviour is testable without a
browser.

Three kinds are supported:

``openapi``
    A specification from a URL or a local path, or an inline spec dict.
``mcp``
    An MCP server addressed by transport — stdio command, SSE or streamable
    HTTP URL.
``python``
    A module, class or function already importable in the server process.

Preview never mutates the registry.  Registration passes the picked names as
the registry's own ``include`` filter, so a source cannot register a tool the
operator did not tick.
"""

from __future__ import annotations

import base64
import importlib
import inspect
import re
from typing import TYPE_CHECKING, Any

from ..utils import HttpClientConfig

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry

_SUPPORTED_KINDS = ("openapi", "mcp", "python")
_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


class SourceError(ValueError):
    """Raised when a source description is unusable.

    The message is shown to the operator, so it names what is wrong rather
    than where in the code it was noticed.
    """


#: The character set OpenAI and Anthropic accept for a function/tool name.
#: Gemini is looser (dots are allowed) but a name that passes this passes all
#: three, so the panel reports against the strictest rule it knows.
_STRICT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def invalid_tool_names(names: list[str]) -> list[str]:
    """Return the names some model APIs would reject.

    Server-provided names may contain ``/`` (an MCP server often groups tools
    as ``fs/read``).  ToolRegistry stores such a name faithfully; the provider
    schemas built from it are then rejected at call time, far from the source.
    The panel surfaces the mismatch when the tools are still being chosen.
    """
    return sorted(name for name in names if not _STRICT_NAME.match(name))


def _require_mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SourceError("Source description must be a JSON object")
    return payload


def _namespace(payload: dict[str, Any]) -> str | None:
    raw = payload.get("namespace")
    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        raise SourceError("'namespace' must be a string")
    return raw


# --------------------------------------------------------------------------
# OpenAPI
# --------------------------------------------------------------------------


def _request_headers(payload: dict[str, Any]) -> dict[str, str] | None:
    """Build request headers from ``headers`` and the ``auth`` block.

    ``auth`` is the panel's flattened way of saying "this source needs a
    credential": ``{"type": "bearer", "token": ...}`` or ``{"type": "basic",
    "username": ..., "password": ...}``.  An explicit ``Authorization`` header
    wins over ``auth`` so an operator can send a scheme the panel does not
    model.  Returns ``None`` when the source needs no headers at all.
    """
    raw_headers = payload.get("headers") or {}
    if not isinstance(raw_headers, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in raw_headers.items()
    ):
        raise SourceError("'headers' must be an object of string values")
    headers = dict(raw_headers)

    auth = payload.get("auth")
    if auth is None:
        return headers or None
    if not isinstance(auth, dict):
        raise SourceError("'auth' must be an object")
    auth_type = auth.get("type", "none")
    if auth_type in (None, "none", ""):
        return headers or None

    if any(key.lower() == "authorization" for key in headers):
        return headers

    if auth_type == "bearer":
        token = auth.get("token")
        if not isinstance(token, str) or not token:
            raise SourceError("Bearer authentication needs a 'token'")
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "basic":
        username = auth.get("username")
        password = auth.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            raise SourceError("Basic authentication needs 'username' and 'password'")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    else:
        raise SourceError(f"Unsupported auth type '{auth_type}'")
    return headers or None


def _load_openapi(payload: dict[str, Any]) -> tuple[dict[str, Any], str, str | None]:
    """Return ``(spec, base_url, spec_url)`` for an OpenAPI payload."""
    from ..integrations.openapi.utils import (
        extract_base_url_from_specs,
        load_openapi_spec,
    )

    spec_url = payload.get("spec_url")
    spec = payload.get("spec")
    if spec is not None and not isinstance(spec, dict):
        raise SourceError("'spec' must be a JSON object")
    if spec is None:
        if not spec_url or not isinstance(spec_url, str):
            raise SourceError("Provide either 'spec_url' or an inline 'spec'")
        try:
            spec = load_openapi_spec(spec_url)
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            raise SourceError(f"Could not load the OpenAPI spec: {exc}") from exc
    if not isinstance(spec, dict) or not spec.get("paths"):
        raise SourceError("The OpenAPI spec has no 'paths' to register")

    base_url = payload.get("base_url") or extract_base_url_from_specs(spec)
    if not base_url:
        raise SourceError("The spec has no servers[] entry; pass 'base_url' explicitly")
    return spec, str(base_url), spec_url if isinstance(spec_url, str) else None


def _openapi_entries(
    payload: dict[str, Any], registry: ToolRegistry
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from ..integrations.openapi.integration import OpenAPITool

    spec, base_url, spec_url = _load_openapi(payload)
    client = HttpClientConfig(base_url=base_url, headers=_request_headers(payload))
    namespace = _namespace(payload)
    entries: list[dict[str, Any]] = []
    for path, operations in spec.get("paths", {}).items():
        if not isinstance(operations, dict):
            continue
        for method, operation in operations.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            tool = OpenAPITool.from_openapi_spec(
                client,
                path,
                method.lower(),
                operation,
                namespace=namespace,
                sep=registry.name_sep,
            )
            entries.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameter_count": len(
                        (tool.parameters or {}).get("properties", {})
                    ),
                    "method": method.upper(),
                    "path": path,
                }
            )
    info = {
        "base_url": base_url,
        "spec_url": spec_url,
        "server_count": len(spec.get("servers") or []),
    }
    return entries, info


# --------------------------------------------------------------------------
# MCP
# --------------------------------------------------------------------------


def _mcp_transport(payload: dict[str, Any]) -> str | dict[str, Any]:
    """Build the transport value from the panel's flat form fields."""
    transport = payload.get("transport")
    if isinstance(transport, (str, dict)) and transport:
        return transport

    url = payload.get("url")
    command = payload.get("command")
    if url:
        if not isinstance(url, str):
            raise SourceError("'url' must be a string")
        return url
    if command:
        if not isinstance(command, str):
            raise SourceError("'command' must be a string")
        args = payload.get("args") or []
        if isinstance(args, str):
            args = args.split()
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise SourceError("'args' must be a list of strings")
        env = payload.get("env") or {}
        if not isinstance(env, dict):
            raise SourceError("'env' must be an object of string values")
        built: dict[str, Any] = {"command": command, "args": args}
        if env:
            built["env"] = env
        return built
    raise SourceError("Provide an MCP 'url', or a 'command' with optional 'args'")


def _mcp_entries(
    payload: dict[str, Any], registry: ToolRegistry
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import asyncio

    from .._async_runtime import AsyncRuntime
    from ..integrations.mcp.client import MCPClient
    from .._names import qualified_tool_name

    transport = _mcp_transport(payload)
    headers = _request_headers(payload)
    namespace = _namespace(payload)

    async def _list() -> Any:
        async with MCPClient(transport, headers=headers) as client:
            return await client.list_tools()

    try:
        tools = AsyncRuntime.run_sync(_list())
    except asyncio.CancelledError:  # pragma: no cover - defensive
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        detail = str(exc).strip() or type(exc).__name__
        hint = ""
        if isinstance(transport, str) and transport.startswith(("http://", "https://")):
            # A 401 from an HTTP transport often arrives without a message.
            hint = " (an HTTP server that requires a token reports this way; set Authentication)"
        raise SourceError(f"Could not reach the MCP server: {detail}{hint}") from exc

    entries = []
    for spec in tools:
        raw_name = spec.name
        schema = getattr(spec, "input_schema", None) or getattr(spec, "inputSchema", {})
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        entries.append(
            {
                "name": qualified_tool_name(raw_name, namespace, registry.name_sep),
                "description": spec.description or "",
                "parameter_count": len(properties),
            }
        )
    return entries, {"transport": transport}


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------


def _import_python_target(
    payload: dict[str, Any],
) -> tuple[Any, Any, str | None]:
    """Return ``(module, target, object_path)`` or explain why not."""
    module_name = payload.get("module")
    if not module_name or not isinstance(module_name, str):
        raise SourceError("'module' is required, e.g. 'mypkg.tools'")
    object_path = payload.get("object")
    if object_path is not None and not isinstance(object_path, str):
        raise SourceError("'object' must be a string")

    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        raise SourceError(f"Could not import '{module_name}': {exc}") from exc

    if not object_path:
        return module, module, None
    try:
        return module, getattr(module, object_path), object_path
    except AttributeError as exc:
        raise SourceError(f"'{module_name}' has no attribute '{object_path}'") from exc


def _python_candidates(module: Any, target: Any, label: str) -> list[tuple[str, Any]]:
    """Collect the callables a module, class or function contributes."""
    if inspect.isfunction(target):
        return [(target.__name__, target)]
    if inspect.isclass(target):
        candidates = [
            (name, member)
            for name, member in inspect.getmembers(target, inspect.isfunction)
            if not name.startswith("_")
        ]
        if not candidates:
            raise SourceError(f"'{label}' has no public methods")
        return candidates

    candidates = [
        (name, member)
        for name, member in inspect.getmembers(module, inspect.isfunction)
        if not name.startswith("_") and member.__module__ == module.__name__
    ]
    if not candidates:
        raise SourceError(f"'{label}' defines no public functions; name an 'object'")
    return candidates


def _parameter_count(func: Any) -> int:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return 0
    kinds = (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.KEYWORD_ONLY,
    )
    return len([p for p in signature.parameters.values() if p.kind in kinds])


def _python_entries(
    payload: dict[str, Any], registry: ToolRegistry
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    module, target, object_path = _import_python_target(payload)
    module_name = payload["module"]
    candidates = _python_candidates(module, target, object_path or module_name)
    entries = [
        {
            "name": name,
            "description": inspect.getdoc(func) or "",
            "parameter_count": _parameter_count(func),
        }
        for name, func in candidates
    ]
    return entries, {"module": module_name, "object": object_path}


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def preview_source(registry: ToolRegistry, kind: str, payload: Any) -> dict[str, Any]:
    """List what a source offers without registering anything.

    Args:
        registry: Registry whose naming rules (``name_sep``) shape the names.
        kind: One of ``"openapi"``, ``"mcp"`` or ``"python"``.
        payload: Source description; see the module docstring.

    Returns:
        ``{"kind", "tools", "count", "already_registered", "info"}`` where
        each tool entry carries ``name``, ``description``,
        ``parameter_count`` and ``registered``.

    Raises:
        SourceError: When the source cannot be reached or the description is
            incomplete.
    """
    if kind not in _SUPPORTED_KINDS:
        raise SourceError(
            f"Unsupported source kind '{kind}'; expected one of "
            + ", ".join(_SUPPORTED_KINDS)
        )
    data = _require_mapping(payload)

    if kind == "openapi":
        entries, info = _openapi_entries(data, registry)
    elif kind == "mcp":
        entries, info = _mcp_entries(data, registry)
    else:
        entries, info = _python_entries(data, registry)

    known = set(registry.list_tools(include_disabled=True))
    for entry in entries:
        entry["registered"] = entry["name"] in known
    return {
        "kind": kind,
        "tools": entries,
        "count": len(entries),
        "already_registered": sum(1 for e in entries if e["registered"]),
        "invalid_names": invalid_tool_names([e["name"] for e in entries]),
        "info": info,
    }


def _validated_selection(data: dict[str, Any]) -> list[str] | None:
    selected = data.get("selected")
    if selected is None:
        return None
    if not isinstance(selected, list) or not all(
        isinstance(name, str) for name in selected
    ):
        raise SourceError("'selected' must be a list of tool names")
    return selected


def _register_openapi_source(
    registry: ToolRegistry,
    data: dict[str, Any],
    selected: list[str] | None,
    namespace: str | None,
) -> None:
    spec, base_url, spec_url = _load_openapi(data)
    client = HttpClientConfig(base_url=base_url, headers=_request_headers(data))
    kwargs: dict[str, Any] = {
        "source": "openapi",
        "openapi_spec": spec,
        "namespace": namespace or False,
        "spec_url": spec_url,
    }
    if selected is not None:
        kwargs["include"] = selected
    registry.register(client, **kwargs)


def _register_mcp_source(
    registry: ToolRegistry,
    data: dict[str, Any],
    selected: list[str] | None,
    namespace: str | None,
) -> None:
    kwargs: dict[str, Any] = {"source": "mcp", "namespace": namespace or False}
    headers = _request_headers(data)
    if headers:
        kwargs["headers"] = headers
    if selected is not None:
        kwargs["include"] = selected
    registry.register(_mcp_transport(data), **kwargs)


def _register_python_source(
    registry: ToolRegistry,
    data: dict[str, Any],
    selected: list[str] | None,
    namespace: str | None,
) -> None:
    entries, _info = _python_entries(data, registry)
    wanted = {entry["name"] for entry in entries}
    if selected is not None:
        wanted &= set(selected)
        if not wanted:
            raise SourceError("None of the selected names exist in that module")

    module, target, _object_path = _import_python_target(data)
    if inspect.isfunction(target):
        registry.register(target, name=target.__name__, namespace=namespace or False)
        return
    for name, member in inspect.getmembers(target, inspect.isfunction):
        if name in wanted:
            registry.register(member, name=name, namespace=namespace or False)


def register_tools(registry: ToolRegistry, kind: str, payload: Any) -> dict[str, Any]:
    """Register the picked tools of a source.

    Args:
        registry: Target registry.
        kind: One of ``"openapi"``, ``"mcp"`` or ``"python"``.
        payload: Source description plus ``selected`` — the list of preview
            names to keep, or ``None`` for every tool the source offers —
            and an optional ``namespace``.

    Returns:
        ``{"kind", "registered", "count", "namespace"}``.

    Raises:
        SourceError: When the source cannot be reached, the description is
            incomplete, or the selection names nothing the source offers.
    """
    if kind not in _SUPPORTED_KINDS:
        raise SourceError(
            f"Unsupported source kind '{kind}'; expected one of "
            + ", ".join(_SUPPORTED_KINDS)
        )
    data = _require_mapping(payload)
    selected = _validated_selection(data)
    namespace = _namespace(data)
    before = set(registry.list_tools(include_disabled=True))

    if kind == "openapi":
        _register_openapi_source(registry, data, selected, namespace)
    elif kind == "mcp":
        _register_mcp_source(registry, data, selected, namespace)
    else:
        _register_python_source(registry, data, selected, namespace)

    added = sorted(set(registry.list_tools(include_disabled=True)) - before)
    return {
        "kind": kind,
        "registered": added,
        "count": len(added),
        "namespace": namespace,
        "invalid_names": invalid_tool_names(added),
    }
