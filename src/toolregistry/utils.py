import base64
import dataclasses
import fnmatch
import hashlib
import json
import math
import re
import uuid
import warnings
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Literal, overload

from ._vendor.httpclient import AsyncClient, Client
from ._warnings import warn_at_user_frame


def generate_invocation_id(prefix: Literal["bat", "ptc", "sig"] = "sig") -> str:
    """Generate a unique invocation ID for grouping related tool calls.

    Prefixes:
        - ``tr_bat_`` — batch execution via ``execute_tool_calls()``
        - ``tr_ptc_`` — PTC code execution via ``PtcTool``
        - ``tr_sig_`` — single invocation via ``registry.invoke()``

    Args:
        prefix: One of ``"bat"``, ``"ptc"``, ``"sig"``.

    Returns:
        A unique ID like ``"tr_bat_a1b2c3d4"``.
    """
    return f"tr_{prefix}_{uuid.uuid4().hex[:8]}"


class _BaseUrlClient:
    """Sync HTTP client wrapper that prepends base_url to relative URLs."""

    def __init__(self, client: Client, base_url: str) -> None:
        self._client = client
        self._base_url = base_url

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return self._base_url + path

    def get(self, url: str, **kwargs: Any) -> Any:
        return self._client.get(self._url(url), **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        return self._client.request(method, self._url(url), **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self._client.post(self._url(url), **kwargs)

    def put(self, url: str, **kwargs: Any) -> Any:
        return self._client.put(self._url(url), **kwargs)

    def patch(self, url: str, **kwargs: Any) -> Any:
        return self._client.patch(self._url(url), **kwargs)

    def delete(self, url: str, **kwargs: Any) -> Any:
        return self._client.delete(self._url(url), **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "_BaseUrlClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class _BaseUrlAsyncClient:
    """Async HTTP client wrapper that prepends base_url to relative URLs."""

    def __init__(self, client: AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url

    def _url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return self._base_url + path

    async def get(self, url: str, **kwargs: Any) -> Any:
        return await self._client.get(self._url(url), **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        return await self._client.request(method, self._url(url), **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        return await self._client.post(self._url(url), **kwargs)

    async def put(self, url: str, **kwargs: Any) -> Any:
        return await self._client.put(self._url(url), **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Any:
        return await self._client.patch(self._url(url), **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        return await self._client.delete(self._url(url), **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "_BaseUrlAsyncClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()


class HttpClientConfig:
    """Container for HTTP client configuration.

    Creates zero-dependency HTTP clients with base URL support,
    connection pooling, and both sync/async interfaces.

    Args:
        base_url: The base URL for the API. This is required.
        headers: Custom request headers. Default is None.
        timeout: Request timeout in seconds. Default is 10.0.
        auth: Basic authentication credentials (username, password). Default is None.
        cookies: Initial cookies to send with requests. The underlying
            client maintains a persistent cookie jar — cookies from
            ``Set-Cookie`` response headers are accumulated across
            requests on the same persistent client. Default is None.
        **extra_options: Additional client parameters (e.g. verify, proxy, pool_size).
    """

    # Known parameters that map directly to Client/AsyncClient constructor
    _KNOWN_CLIENT_PARAMS = {"verify", "proxy", "pool_size", "max_redirects"}

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        auth: tuple[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        **extra_options: Any,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.auth = auth
        self.cookies = cookies
        self.extra_options = extra_options
        self._sync_client: _BaseUrlClient | None = None
        self._async_client: _BaseUrlAsyncClient | None = None

    def _client_kwargs(self) -> dict[str, Any]:
        """Build kwargs dict for Client/AsyncClient constructor."""
        kwargs: dict[str, Any] = {
            "headers": self.headers,
            "timeout": self.timeout,
            "auth": self.auth,
            "cookies": self.cookies,
        }
        for key in self._KNOWN_CLIENT_PARAMS:
            if key in self.extra_options:
                kwargs[key] = self.extra_options[key]
        return kwargs

    @overload
    def to_client(self, use_async: Literal[False]) -> _BaseUrlClient: ...

    @overload
    def to_client(self, use_async: Literal[True]) -> _BaseUrlAsyncClient: ...

    def to_client(self, use_async: bool = False):
        """Create a new HTTP client instance.

        Args:
            use_async: Whether to create an asynchronous client. Default is False.

        Returns:
            A _BaseUrlClient or _BaseUrlAsyncClient wrapping the underlying
            zero-dependency client with base URL support.
        """
        return self._make_client(use_async=use_async)

    def _make_client(self, use_async: bool = False):
        """Create a new HTTP client instance.

        Args:
            use_async: Whether to create an asynchronous client.

        Returns:
            A _BaseUrlClient or _BaseUrlAsyncClient instance.
        """
        kwargs = self._client_kwargs()
        if use_async:
            raw = AsyncClient(**kwargs)
            return _BaseUrlAsyncClient(raw, self.base_url)
        else:
            raw = Client(**kwargs)
            return _BaseUrlClient(raw, self.base_url)

    @overload
    def get_persistent_client(
        self, use_async: Literal[False] = False
    ) -> _BaseUrlClient: ...

    @overload
    def get_persistent_client(
        self, use_async: Literal[True] = ...
    ) -> _BaseUrlAsyncClient: ...

    def get_persistent_client(self, use_async: bool = False):
        """Get or create a persistent client instance.

        Unlike ``to_client()``, this method reuses the same client across
        multiple calls, enabling HTTP connection pooling.

        Args:
            use_async: Whether to return an async client.

        Returns:
            A persistent _BaseUrlClient or _BaseUrlAsyncClient instance.
        """
        if use_async:
            if self._async_client is None:
                self._async_client = self._make_client(use_async=True)
            return self._async_client
        else:
            if self._sync_client is None:
                self._sync_client = self._make_client(use_async=False)
            return self._sync_client

    def close(self):
        """Close persistent clients (sync).

        Only closes the sync client. Use ``close_async()`` to properly
        close the async client.
        """
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    async def close_async(self):
        """Close all persistent clients."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    # -- Pickling support (for ProcessPoolBackend) ------------------

    def __getstate__(self) -> dict:
        """Drop live HTTP clients before pickling.

        The config (base_url, headers, timeout, auth, extra_options)
        is preserved.  Live ``_sync_client`` / ``_async_client``
        (holding thread locks and connection pools) are dropped.
        The worker process will recreate them lazily via
        ``get_persistent_client()``.
        """
        return {
            "base_url": self.base_url,
            "headers": self.headers,
            "timeout": self.timeout,
            "auth": self.auth,
            "cookies": self.cookies,
            "extra_options": self.extra_options,
        }

    def __setstate__(self, state: dict) -> None:
        """Restore config; clients will be created lazily on first use."""
        self.base_url = state["base_url"]
        self.headers = state["headers"]
        self.timeout = state["timeout"]
        self.auth = state["auth"]
        self.cookies = state.get("cookies")
        self.extra_options = state["extra_options"]
        self._sync_client = None
        self._async_client = None


def HttpxClientConfig(*args: Any, **kwargs: Any) -> HttpClientConfig:
    """Deprecated alias for HttpClientConfig.

    .. deprecated::
        Use ``HttpClientConfig`` instead. ``HttpxClientConfig`` will be
        removed in a future release.
    """
    warnings.warn(
        "HttpxClientConfig is deprecated, use HttpClientConfig instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return HttpClientConfig(*args, **kwargs)


def normalize_tool_name(name: str) -> str:
    """Normalize tool name to snake_case format and remove dots and spaces.
    Also handles OpenAPI-style duplicate names like 'add_add_get' by converting to 'add_get'.

    Args:
        name: Original tool name in various formats (including CamelCase, UpperCamelCase, or containing spaces)

    Returns:
        str: Normalized name in snake_case without dots or spaces
    """
    # First check for OpenAPI-style duplicate names (e.g. "add_add_get")
    openapi_pattern = r"^([a-zA-Z0-9]+)_\1_([a-zA-Z0-9]+)$"
    match = re.match(openapi_pattern, name)
    if match:
        return f"{match.group(1)}_{match.group(2)}"

    # Replace all special chars (., -, @, etc.) with single underscore
    name = re.sub(r"[.\-@]+", "_", name)

    # Remove spaces and collapse multiple spaces into a single space
    name = re.sub(r"\s+", " ", name).strip()

    # Replace spaces with underscores
    name = name.replace(" ", "_")

    # Convert CamelCase and UpperCamelCase to snake_case
    # Handles all cases including:
    # XMLParser -> xml_parser
    # getUserIDFromDB -> get_user_id_from_db
    # HTTPRequest -> http_request
    name = re.sub(r"(?<!^)(?=[A-Z][a-z])|(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()

    # Collapse multiple underscores into single underscore
    return re.sub(r"_+", "_", name)


def _as_pattern_list(value: str | list[str] | None) -> list[str] | None:
    """Normalize an ``include`` / ``exclude`` argument to a pattern list.

    A bare string is a single pattern, not an iterable of characters.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


def _name_spellings(raw_name: str, namespaced_name: str) -> tuple[str, ...]:
    """Return the name spellings a filter pattern may match.

    The source-advertised name and the registered name are matched as-is,
    plus their snake_case normalizations.  Order is preserved and
    duplicates are dropped.
    """
    spellings = (
        raw_name,
        namespaced_name,
        normalize_tool_name(raw_name),
        normalize_tool_name(namespaced_name),
    )
    return tuple(dict.fromkeys(spellings))


class ToolNameFilter:
    """Include/exclude filter applied when registering remote tools.

    Patterns are matched with :func:`fnmatch.fnmatchcase` against four
    spellings of each candidate name: the raw remote tool name (the name
    the source advertises, e.g. the MCP tool name or the OpenAPI
    ``operationId``), the final post-namespace name (e.g.
    ``gh-list_issues``), and the :func:`normalize_tool_name` form of each.
    A pattern therefore matches a tool when it matches any spelling, so
    ``bash-execute``, ``bash_execute``, ``hub-bash_execute``, and
    ``hub_bash_execute`` all select the same tool.

    ``include`` and ``exclude`` are mutually exclusive.  ``None`` means the
    corresponding side is not filtered; an empty list matches nothing, so
    ``include=[]`` drops every tool.  A bare string is treated as a
    single-pattern list, so a one-item JSON/YAML ``include: name`` is not
    mistaken for an iterable of characters.

    Matching is case-sensitive (:func:`fnmatch.fnmatchcase`), unlike
    ``discover_tools`` / ``call_deferred``, which fold case.  Write
    patterns in the case the source advertises.

    The normalized spelling is not unique.  When a source advertises two
    names that normalize to the same string (for example ``x-y`` and
    ``x_y``), a pattern written in that spelling selects both tools.  Use
    the raw or post-namespace spelling to narrow to one of them.

    Args:
        include: Names or glob patterns to keep.  When given, a tool is
            kept only if one of its spellings matches a pattern.
        exclude: Names or glob patterns to drop.  When given, a tool is
            dropped if one of its spellings matches a pattern.

    Raises:
        ValueError: If both ``include`` and ``exclude`` are given.
    """

    def __init__(
        self,
        include: str | list[str] | None = None,
        exclude: str | list[str] | None = None,
    ) -> None:
        if include is not None and exclude is not None:
            raise ValueError(
                "include and exclude are mutually exclusive; pass only one."
            )
        self.include = _as_pattern_list(include)
        self.exclude = _as_pattern_list(exclude)

    def accepts(self, raw_name: str, namespaced_name: str) -> bool:
        """Return whether a tool passes the filter.

        Args:
            raw_name: The remote tool name before namespace handling.
            namespaced_name: The final registered name (``raw_name`` plus
                any namespace prefix).

        Returns:
            True if the tool should be registered, False if it must be
            dropped.
        """
        candidates = _name_spellings(raw_name, namespaced_name)
        if self.include is not None:
            return any(
                fnmatch.fnmatchcase(name, pattern)
                for pattern in self.include
                for name in candidates
            )
        if self.exclude is not None:
            return not any(
                fnmatch.fnmatchcase(name, pattern)
                for pattern in self.exclude
                for name in candidates
            )
        return True

    def warn_if_all_filtered_out(
        self,
        *,
        total: int,
        accepted: int,
        source: str,
    ) -> None:
        """Warn when an active filter leaves none of *total* candidates.

        A filter that leaves nothing registered is almost always a
        configuration mistake: an empty list, a bare string, or a pattern
        spelled differently from the names the source advertises.  Without
        this warning registration succeeds and silently produces an empty
        source.

        Args:
            total: Number of candidate tools the source offered.
            accepted: Number of candidates that passed this filter.
            source: Source label used in the message, e.g. ``"MCP"``.

        Warns:
            UserWarning: If a filter is active, *total* is non-zero, and
                *accepted* is zero.
        """
        if self.include is None and self.exclude is None:
            return
        if total <= 0 or accepted > 0:
            return
        if self.include is not None:
            detail = f"include={self.include!r} matched none of {total} tool(s)"
        else:
            detail = f"exclude={self.exclude!r} excluded all {total} tool(s)"
        # Attribute the warning to the caller rather than the integration
        # internals; a fixed stacklevel cannot follow the async bridge.
        warn_at_user_frame(
            f"{source} registration filter {detail}; nothing was registered.",
            UserWarning,
        )


def compute_schema_hash(parameters: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hex digest of a JSON Schema dict.

    Args:
        parameters: The JSON Schema dict (typically ``Tool.parameters``).

    Returns:
        A 64-character lowercase hex string.
    """
    canonical = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def utc_iso_now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _replace_non_finite(value: Any) -> Any:
    """Return *value* with non-finite floats replaced by ``None``.

    Walks the JSON containers ``json`` traverses itself.  Set elements and
    dataclass fields are projected by :class:`ToolResultJSONEncoder`, which
    sanitizes its own output, so they are left untouched here.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {key: _replace_non_finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_replace_non_finite(item) for item in value]
    return value


class ToolResultJSONEncoder(json.JSONEncoder):
    """JSON encoder for values returned by tools.

    Projects common non-JSON-native Python values to a JSON-safe
    representation.  ``json`` traverses containers itself, so this only
    needs to handle the leaf values it cannot serialize.

    Handled values:

    - ``Enum`` members -> their ``.value``
    - ``pathlib.Path`` -> ``str``
    - ``Decimal`` / ``UUID`` -> ``str``
    - ``datetime`` / ``date`` / ``time`` -> ISO 8601 string
    - ``bytes`` -> base64-encoded ASCII string
    - ``set`` / ``frozenset`` -> JSON array, ordered by ``repr`` so the
      encoding is reproducible across processes for orderable and
      mixed-type elements alike (tuples are native to JSON)
    - dataclass instances -> :func:`dataclasses.asdict`
    - Pydantic v2 models (``model_dump``), v1 models (``dict``), any
      object exposing a zero-argument ``to_dict`` -> ``dict``, and
      array-like objects exposing ``tolist`` (numpy arrays, torch
      tensors) -> list

    Whatever ``tolist`` returns is serialized by ``json`` normally, so a
    non-native element inside it is routed back through this encoder.

    Non-finite floats (``NaN``, ``Infinity``, ``-Infinity``) are written as
    ``null``.  ``json`` would otherwise emit the bare constants, which are
    not valid JSON: ``JSON.parse``, Go's ``encoding/json`` and serde all
    reject them, so a tool returning a metric computed from an empty set
    would produce a body a conforming client cannot read.  FastAPI's
    encoder and the JSON spec's recommendation both use ``null``.

    Anything else has no JSON projection and raises ``TypeError``.
    """

    def iterencode(self, o: Any, _one_shot: bool = False):  # noqa: ANN401
        """Encode *o* after replacing non-finite floats with ``null``."""
        return super().iterencode(_replace_non_finite(o), _one_shot)

    def default(self, o: Any) -> Any:
        """Project *o* to JSON-native values, sanitising non-finite floats."""
        return _replace_non_finite(self._project(o))

    def _project(self, o: Any) -> Any:
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, (Decimal, uuid.UUID)):
            return str(o)
        if isinstance(o, (datetime, date, time)):
            return o.isoformat()
        if isinstance(o, bytes):
            return base64.b64encode(o).decode("ascii")
        if isinstance(o, (set, frozenset)):
            # A total order: ``repr`` is always a string, so mixed-type
            # elements sort deterministically instead of following
            # interpreter (process-seeded) iteration order.
            return sorted(o, key=repr)
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        for attr in ("model_dump", "to_dict", "dict", "tolist"):
            method = getattr(o, attr, None)
            if callable(method):
                return method()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


# Types that may be emitted as a bare string without JSON-quoting at the
# top level: their ``str()`` already matches the encoder's projection, so
# the historical plain-string form is preserved.  ``datetime`` is excluded
# even though it subclasses ``date`` -- ``str()`` uses a space separator
# while ``isoformat()`` uses ``T``.  ``Enum`` is handled before this
# allowlist (see ``encode_tool_result``) so a str-mixin member is not
# swallowed by the plain-``str`` branch: ``str()`` yields ``Color.RED`` /
# ``S.A``, exactly the unparseable forms this encoder exists to remove.
# ``bytes`` is likewise excluded on purpose.
_STR_LIKE_SCALARS = (str, Path, Decimal, uuid.UUID, date, time)


def encode_tool_result(result: Any, *, tool_name: str = "") -> str:
    """Encode a tool result to a string suitable for the wire.

    Plain strings pass through unchanged.  Values in the str-like scalar
    allowlist keep their historical ``str()`` textual form.  ``Enum``
    members are projected through ``.value`` at the top level, matching
    their nested projection; this also covers ``IntEnum`` and ``StrEnum``,
    whose ``int`` / ``str`` base would otherwise let the plain scalar
    branch return the bare member.  Everything else -- including ``bytes``
    or ``datetime`` -- is serialized with :class:`ToolResultJSONEncoder`,
    so dataclasses, Pydantic models, paths, and other common types produce
    valid JSON instead of Python ``repr`` text, and the top-level and
    nested projections agree.

    Args:
        result: Raw value returned by a tool.
        tool_name: Tool name, used in the error message when *result* (or
            a value nested inside it) cannot be encoded.

    Returns:
        The encoded result string.

    Raises:
        TypeError: If *result* has no JSON projection.  The message names
            the tool and the offending type, and suggests how to make the
            value encodable.
    """
    if isinstance(result, Enum):
        # Must precede the ``str`` check: ``StrEnum`` (and any
        # ``str``-mixin enum) is a ``str`` instance, and returning the
        # member would put ``S.A`` on the wire instead of ``"a"``.
        return json.dumps(result.value, cls=ToolResultJSONEncoder)
    if isinstance(result, str):
        return result
    if isinstance(result, _STR_LIKE_SCALARS) and not isinstance(result, datetime):
        return str(result)
    try:
        return json.dumps(result, cls=ToolResultJSONEncoder)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"Tool {tool_name!r} returned a value that cannot be encoded to JSON "
            f"({exc}). Add a to_dict() or model_dump() method to the returned "
            f"type, expose tolist(), or return a str."
        ) from exc
