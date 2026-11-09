"""Inspect and register tools from a source, on behalf of the admin panel.

The panel's Register section needs two things the library did not expose as
data: a list of the tools a *source* offers before anything is registered, and
a way to register only the ones the operator picked.  Both live here so the
HTTP layer stays a thin adapter and the behaviour is testable without a
browser.

Three kinds are supported:

``openapi``
    A specification from an ``http``/``https`` URL, or an inline spec dict.
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

from ..utils import HttpClientConfig, OpenAPIPathError

if TYPE_CHECKING:
    from ..tool_registry import ToolRegistry

_SUPPORTED_KINDS = ("openapi", "mcp", "python")
#: Operations the OpenAPI integration turns into tools.  It registers
#: ``get``/``post``/``put``/``delete`` only, so preview and registration both
#: ignore the other methods; a ``patch`` operation would create no tool and
#: its schema is not inspected (#430).
_HTTP_METHODS = {"get", "post", "put", "delete"}


class SourceError(ValueError):
    """Raised when a source description is unusable.

    The message is shown to the operator, so it names what is wrong rather
    than where in the code it was noticed.
    """


#: Shown when the outbound address policy refuses an address.  The panel
#: serves local APIs, so the operator needs the switch that changes the
#: policy, not just the fact that the address was refused.
_PRIVATE_HOSTS_HINT = (
    "That address is not publicly routable (loopback, link-local, private "
    "or another reserved range). Start the admin panel with "
    "allow_private_hosts=True "
    "(registry.enable_admin(allow_private_hosts=True)) to allow it."
)


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


def _validate_spec_url(spec_url: str, *, allow_private_hosts: bool = False) -> str:
    """Refuse a ``spec_url`` the panel must not fetch on the caller's behalf.

    The panel is reachable without a token by default on localhost, so a URL
    it loads is an outbound request made for an anonymous caller.  The shared
    :func:`~toolregistry.integrations.openapi.utils.validate_spec_url` keeps
    the rule in one place, because a refresh fetches the stored URL again.

    Args:
        spec_url: The payload's ``spec_url`` value.
        allow_private_hosts: Whether the operator started the panel with
            ``enable_admin(allow_private_hosts=True)``.

    Returns:
        ``spec_url`` unchanged when it is allowed.

    Raises:
        SourceError: When the URL is malformed, its scheme is not
            ``http``/``https``, it names no host, or the outbound address
            policy refuses it.  A refused private address is reported with
            the switch that allows it.
    """
    from .._netpolicy import PrivateAddressError, UnsafeAddressError
    from ..integrations.openapi.utils import validate_spec_url

    try:
        return validate_spec_url(spec_url, allow_private_hosts=allow_private_hosts)
    except PrivateAddressError:
        raise SourceError(_PRIVATE_HOSTS_HINT) from None
    except UnsafeAddressError as exc:
        # A malformed URL or a name that does not resolve; the switch would
        # not help, so the policy's own message is the useful one.
        raise SourceError(str(exc)) from exc
    except ValueError as exc:
        raise SourceError(str(exc)) from exc


def _checked_base_url(value: str, *, allow_private_hosts: bool) -> str:
    """Return *value* when the outbound address policy allows it."""
    from .._netpolicy import (
        PrivateAddressError,
        UnsafeAddressError,
        validate_outbound_url,
    )

    try:
        validate_outbound_url(value, allow_private_hosts=allow_private_hosts)
    except PrivateAddressError:
        raise SourceError(f"'base_url' is refused. {_PRIVATE_HOSTS_HINT}") from None
    except UnsafeAddressError as exc:
        raise SourceError(str(exc)) from exc
    return value


def _base_url_from_spec(spec: dict[str, Any], *, allow_private_hosts: bool) -> str:
    """Return the ``servers[0]`` URL when it is allowed.

    Only the entry registration dials is checked.  A document may list
    further entries — a generated spec often appends a local development
    server — and they are never requested, so they must not refuse the
    source.  This is the same narrow rule a refresh applies to a moved
    ``servers[0]`` (#460).

    A templated entry (``https://{region}.example.com``) cannot be dialed
    before substitution, so it is reported as unusable rather than resolved.

    Args:
        spec: The parsed OpenAPI document.
        allow_private_hosts: Whether the operator started the panel with
            ``enable_admin(allow_private_hosts=True)``.

    Returns:
        ``servers[0]`` without a trailing slash.

    Raises:
        SourceError: When the entry is refused, or the spec has no usable
            ``servers[]`` entry.  The two cases are reported differently,
            because only the first one has a switch.
    """
    from .._netpolicy import (
        PrivateAddressError,
        UnsafeAddressError,
        validate_outbound_url,
    )
    from ..integrations.openapi.utils import first_server_url

    base_url = first_server_url(spec)
    if not base_url or "{" in base_url or "}" in base_url:
        raise SourceError("The spec has no servers[] entry; pass 'base_url' explicitly")
    try:
        validate_outbound_url(base_url, allow_private_hosts=allow_private_hosts)
    except PrivateAddressError:
        raise SourceError(
            "The spec's servers[] URL is refused. " + _PRIVATE_HOSTS_HINT
        ) from None
    except UnsafeAddressError as exc:
        raise SourceError(str(exc)) from exc
    return base_url


def _load_openapi(
    payload: dict[str, Any], *, allow_private_hosts: bool = False
) -> tuple[dict[str, Any], str, str | None]:
    """Return ``(spec, base_url, spec_url)`` for an OpenAPI payload.

    Args:
        payload: The panel's source description.
        allow_private_hosts: Accept a ``spec_url``, a ``base_url`` or a
            ``servers[]`` entry that resolves to a loopback, link-local or
            private address.

    Raises:
        SourceError: When the description is incomplete, the spec cannot be
            loaded, or an address it names is refused.
    """
    from ..integrations.openapi.utils import load_openapi_spec, redact_url_userinfo

    spec_url = payload.get("spec_url")
    spec = payload.get("spec")
    if spec_url is not None and not isinstance(spec_url, str):
        raise SourceError("'spec_url' must be a string")
    if spec is not None and not isinstance(spec, dict):
        raise SourceError("'spec' must be a JSON object")
    if spec is None:
        if not spec_url:
            raise SourceError("Provide either 'spec_url' or an inline 'spec'")
        spec_url = _validate_spec_url(spec_url, allow_private_hosts=allow_private_hosts)
        try:
            spec = load_openapi_spec(
                spec_url,
                allow_private_hosts=allow_private_hosts,
                # The panel states its own policy instead of inheriting the
                # loader default: a redirect would be a second request to an
                # address the panel never validated.
                follow_redirects=False,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            detail = redact_url_userinfo(str(exc))
            raise SourceError(f"Could not load the OpenAPI spec: {detail}") from exc
    elif spec_url:
        # An inline spec is not fetched now, but the URL is stored and used
        # by a later refresh; refuse a scheme that refresh must not fetch.
        _validate_spec_url(spec_url, allow_private_hosts=allow_private_hosts)
    if not isinstance(spec, dict) or not spec.get("paths"):
        raise SourceError("The OpenAPI spec has no 'paths' to register")

    explicit_base_url = payload.get("base_url")
    if explicit_base_url:
        if not isinstance(explicit_base_url, str):
            raise SourceError("'base_url' must be a string")
        base_url = _checked_base_url(
            explicit_base_url, allow_private_hosts=allow_private_hosts
        )
    else:
        base_url = _base_url_from_spec(spec, allow_private_hosts=allow_private_hosts)
    return spec, str(base_url), spec_url


try:  # optional dependency: the engine the server validates requests with
    import regex as _PATTERN_ENGINE
except ImportError:  # pragma: no cover - exercised by the fallback test
    _PATTERN_ENGINE = re

#: Schema keywords whose values are data, not subschemas.  A ``pattern``
#: inside them is a literal value, so it is not compiled.
_DATA_KEYWORDS = frozenset({"example", "examples", "default", "enum", "const"})

#: Schema keywords whose values are maps of *names* to subschemas.  The keys
#: are property names (any string, including ``default`` or ``enum``), so
#: the data-keyword skip must not be applied to them.  ``dependentSchemas``
#: is the JSON Schema 2020-12 spelling and ``dependencies`` the draft-04 one;
#: a ``dependencies`` value may also be an array of property names, which the
#: walker ignores because it is not a schema.
_NAME_MAP_KEYWORDS = frozenset(
    {
        "properties",
        "patternProperties",
        "dependentSchemas",
        "dependencies",
        "$defs",
        "definitions",
    }
)

#: Name maps walked by value, in a fixed order for deterministic messages.
#: ``patternProperties`` is absent because its keys are checked as patterns.
_NAME_MAP_WALK = (
    "properties",
    "dependentSchemas",
    "dependencies",
    "$defs",
    "definitions",
)

#: Keywords ``_walk_patterns`` handles itself, so the generic child walk must
#: not visit them a second time.
_HANDLED_KEYWORDS = _NAME_MAP_KEYWORDS | {"pattern"}


def _pattern_schemas(operation: dict[str, Any]) -> list[tuple[str, Any]]:
    """Return the schemas an operation turns into published tool parameters.

    Only the parts ``OpenAPITool.from_openapi_spec`` reads are included: each
    ``parameters[].schema`` and the ``application/json`` request body.  A
    pattern anywhere else in the document never reaches the tool schema.

    Args:
        operation: One OpenAPI operation object.

    Returns:
        ``(schema_path, schema)`` pairs, the path being relative to the
        operation and usable in an operator-facing message.
    """
    schemas: list[tuple[str, Any]] = []
    parameters = operation.get("parameters")
    if isinstance(parameters, list):
        for index, param in enumerate(parameters):
            if not isinstance(param, dict):
                continue
            label = param.get("name", index)
            schemas.append((f"parameters[{label!r}].schema", param.get("schema")))
    request_body = operation.get("requestBody")
    content = request_body.get("content") if isinstance(request_body, dict) else None
    body = content.get("application/json") if isinstance(content, dict) else None
    if isinstance(body, dict):
        schemas.append(
            ("requestBody.content['application/json'].schema", body.get("schema"))
        )
    return schemas


def _record_pattern(
    pattern: Any, path: str, tool_name: str, seen: set[str], failures: list[str]
) -> None:
    """Compile *pattern* and record a failure once per distinct value."""
    if not isinstance(pattern, str) or pattern in seen:
        return
    seen.add(pattern)
    try:
        _PATTERN_ENGINE.compile(pattern)
    except _PATTERN_ENGINE.error as exc:
        failures.append(f"tool '{tool_name}' {path}: {exc}")


def _walk_pattern_properties(
    node: dict[str, Any],
    path: str,
    tool_name: str,
    seen: set[str],
    failures: list[str],
) -> None:
    """Check a ``patternProperties`` map: both its keys and its schemas."""
    pattern_properties = node.get("patternProperties")
    if not isinstance(pattern_properties, dict):
        return
    for key, sub in pattern_properties.items():
        _record_pattern(
            key,
            f"{path}.patternProperties[{key!r}]",
            tool_name,
            seen,
            failures,
        )
        _walk_patterns(
            sub, f"{path}.patternProperties.{key}", tool_name, seen, failures
        )


def _walk_name_map(
    node: dict[str, Any],
    keyword: str,
    path: str,
    tool_name: str,
    seen: set[str],
    failures: list[str],
) -> None:
    """Walk a name map such as ``properties`` or ``$defs``.

    The keys of these maps are names, not schema keywords, so every value is
    walked as a schema even when the name is ``default`` or ``enum``.
    ``dependencies`` may also hold an array of property names, which the walk
    ignores because a string is not a schema.
    """
    name_map = node.get(keyword)
    if not isinstance(name_map, dict):
        return
    for name, sub in name_map.items():
        _walk_patterns(sub, f"{path}.{keyword}.{name}", tool_name, seen, failures)


def _walk_patterns(
    node: Any,
    path: str,
    tool_name: str,
    seen: set[str],
    failures: list[str],
) -> None:
    """Collect uncompilable patterns under *node*, as validation sees them."""
    if isinstance(node, dict):
        _record_pattern(
            node.get("pattern"), f"{path}.pattern", tool_name, seen, failures
        )
        _walk_pattern_properties(node, path, tool_name, seen, failures)
        for keyword in _NAME_MAP_WALK:
            _walk_name_map(node, keyword, path, tool_name, seen, failures)
        for key, value in node.items():
            if key in _HANDLED_KEYWORDS or key in _DATA_KEYWORDS:
                continue
            _walk_patterns(value, f"{path}.{key}", tool_name, seen, failures)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _walk_patterns(value, f"{path}[{index}]", tool_name, seen, failures)


def _check_spec_patterns(
    spec: dict[str, Any], namespace: str | None, registry: ToolRegistry
) -> None:
    """Reject an OpenAPI document whose schemas carry an uncompilable regex.

    A malformed ``pattern`` or ``patternProperties`` key must not reach the
    registry: with the optional ``regex`` package installed every call fails
    closed at request time, and without it the constraint is silently
    ignored.  Preview and registration both call this, so they agree.

    The engine is ``regex`` when installed and stdlib ``re`` otherwise.  The
    fallback is stricter than request-time behaviour without ``regex``: a
    pattern that only ``regex`` accepts (variable-length lookbehind,
    ``\\p{...}``) is rejected rather than later ignored.

    Args:
        spec: The parsed OpenAPI document.
        namespace: Explicit namespace the source was given, if any.
        registry: Registry whose separator shapes the reported tool names.

    Raises:
        SourceError: Naming each tool and schema path with a bad pattern.
    """
    from .._names import qualified_tool_name
    from ..integrations.openapi.integration import _operation_id

    seen: set[str] = set()
    failures: list[str] = []
    for path, operations in spec.get("paths", {}).items():
        if not isinstance(operations, dict):
            continue
        for method, operation in operations.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            tool_name = qualified_tool_name(
                _operation_id(operation, path, method), namespace, registry.name_sep
            )
            for label, schema in _pattern_schemas(operation):
                _walk_patterns(schema, label, tool_name, seen, failures)
    if failures:
        raise SourceError(
            "The OpenAPI spec has patterns that do not compile: " + "; ".join(failures)
        )


def _openapi_entries(
    payload: dict[str, Any],
    registry: ToolRegistry,
    *,
    allow_private_hosts: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from ..integrations.openapi.integration import OpenAPITool

    spec, base_url, spec_url = _load_openapi(
        payload, allow_private_hosts=allow_private_hosts
    )
    client = HttpClientConfig(
        base_url=base_url,
        headers=_request_headers(payload),
        allow_private_hosts=allow_private_hosts,
    )
    namespace = _namespace(payload)
    _check_spec_patterns(spec, namespace, registry)
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


def transport_spawns_process(payload: dict[str, Any]) -> bool:
    """Return whether an MCP source description starts a local process.

    A transport is local unless it is an ``http://`` or ``https://`` URL: the
    MCP client treats every other value — a command dict, a bare script path,
    or a string naming an executable — as a stdio server and runs it.  The HTTP
    layer uses this to require an authenticated operator before executing
    anything the request supplied.

    Args:
        payload: Source description as received from the panel.

    Returns:
        ``True`` when executing the source would spawn a process.

    Raises:
        SourceError: When the payload names no usable transport.  Callers that
            only need the boolean should let the normal handler report it.
    """
    transport = _mcp_transport(payload)
    if isinstance(transport, str):
        return not transport.startswith(("http://", "https://"))
    return True


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
        async with MCPClient(
            transport,
            headers=headers,
            allow_private_hosts=payload.get("allow_private_hosts") is True,
        ) as client:
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


def preview_source(
    registry: ToolRegistry,
    kind: str,
    payload: Any,
    *,
    allow_private_hosts: bool = False,
) -> dict[str, Any]:
    """List what a source offers without registering anything.

    Args:
        registry: Registry whose naming rules (``name_sep``) shape the names.
        kind: One of ``"openapi"``, ``"mcp"`` or ``"python"``.
        payload: Source description; see the module docstring.
        allow_private_hosts: Accept an OpenAPI address that resolves to a
            loopback, link-local or private address.  The admin panel passes
            the switch it was started with.

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
        try:
            entries, info = _openapi_entries(
                data, registry, allow_private_hosts=allow_private_hosts
            )
        except SourceError:
            raise
        except OpenAPIPathError as exc:
            # A rejected operation path is a bad request, not a server fault.
            raise SourceError(str(exc)) from exc
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
    *,
    allow_private_hosts: bool = False,
) -> None:
    spec, base_url, spec_url = _load_openapi(
        data, allow_private_hosts=allow_private_hosts
    )
    _check_spec_patterns(spec, namespace, registry)
    client = HttpClientConfig(
        base_url=base_url,
        headers=_request_headers(data),
        allow_private_hosts=allow_private_hosts,
    )
    kwargs: dict[str, Any] = {
        "source": "openapi",
        "openapi_spec": spec,
        "namespace": namespace or False,
        "spec_url": spec_url,
    }
    if selected is not None:
        kwargs["include"] = selected
    try:
        registry.register(client, **kwargs)
    except SourceError:
        raise
    except OpenAPIPathError as exc:
        # A rejected operation path is a bad request, not a server fault.
        raise SourceError(str(exc)) from exc


def _register_mcp_source(
    registry: ToolRegistry,
    data: dict[str, Any],
    selected: list[str] | None,
    namespace: str | None,
) -> None:
    kwargs: dict[str, Any] = {"source": "mcp", "namespace": namespace or False}
    if data.get("allow_private_hosts") is True:
        kwargs["allow_private_hosts"] = True
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


def register_tools(
    registry: ToolRegistry,
    kind: str,
    payload: Any,
    *,
    allow_private_hosts: bool = False,
) -> dict[str, Any]:
    """Register the picked tools of a source.

    Args:
        registry: Target registry.
        kind: One of ``"openapi"``, ``"mcp"`` or ``"python"``.
        payload: Source description plus ``selected`` — the list of preview
            names to keep, or ``None`` for every tool the source offers —
            and an optional ``namespace``.
        allow_private_hosts: Accept an OpenAPI address that resolves to a
            loopback, link-local or private address, for both the spec fetch
            and the tools' calls.  The admin panel passes the switch it was
            started with.

    Returns:
        ``{"kind", "registered", "count", "namespace", "preserved_overrides"}``.
        ``preserved_overrides`` names the tools whose local override survived
        the re-registration, so the panel can say so instead of silently
        changing what the operator sees.

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
    # A source is registered as a whole, so its tools go through ``register()``,
    # which treats each incoming tool as the new definition and drops the
    # override record.  Snapshot the replacement in force for every overridden
    # name first and put it back afterwards: an override the operator set must
    # outlive a re-registration, exactly as it outlives a remote refresh.
    overrides_before = {
        name: replacement
        for name in registry.list_overrides()
        if (replacement := registry.get_tool(name)) is not None
    }

    if kind == "openapi":
        _register_openapi_source(
            registry,
            data,
            selected,
            namespace,
            allow_private_hosts=allow_private_hosts,
        )
    elif kind == "mcp":
        _register_mcp_source(registry, data, selected, namespace)
    else:
        _register_python_source(registry, data, selected, namespace)

    preserved = sorted(
        name
        for name, override_tool in overrides_before.items()
        if registry._reinstate_override(name, override_tool)
    )
    added = sorted(set(registry.list_tools(include_disabled=True)) - before)
    return {
        "kind": kind,
        "registered": added,
        "count": len(added),
        "namespace": namespace,
        "invalid_names": invalid_tool_names(added),
        "preserved_overrides": preserved,
    }
