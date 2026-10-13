import base64
import dataclasses
import hashlib
import json
import re
import uuid
import warnings
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Literal, overload

from ._vendor.httpclient import AsyncClient, Client


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
    - ``set`` / ``frozenset`` -> JSON array, sorted when the elements are
      orderable so the encoding is reproducible across processes
      (tuples are native to JSON)
    - dataclass instances -> :func:`dataclasses.asdict`
    - Pydantic v2 models (``model_dump``), v1 models (``dict``), any
      object exposing a zero-argument ``to_dict`` -> ``dict``, and
      array-like objects exposing ``tolist`` (numpy arrays, torch
      tensors) -> list

    Whatever ``tolist`` returns is serialized by ``json`` normally, so a
    non-native element inside it is routed back through this encoder.

    Anything else has no JSON projection and raises ``TypeError``.
    """

    def default(self, o: Any) -> Any:
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
            try:
                return sorted(o)
            except TypeError:
                # Elements are not mutually orderable; keep them in
                # iteration order rather than failing.
                return list(o)
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
# while ``isoformat()`` uses ``T``.  ``Enum`` and ``bytes`` are excluded
# because ``str()`` yields ``Color.RED`` / ``b'...'``: exactly the
# unparseable forms this encoder exists to remove.
_STR_LIKE_SCALARS = (str, Path, Decimal, uuid.UUID, date, time)


def encode_tool_result(result: Any, *, tool_name: str = "") -> str:
    """Encode a tool result to a string suitable for the wire.

    Plain strings pass through unchanged.  Values in the str-like scalar
    allowlist keep their historical ``str()`` textual form.  Everything
    else -- including a bare ``Enum``, ``bytes`` or ``datetime`` -- is
    serialized with :class:`ToolResultJSONEncoder`, so dataclasses,
    Pydantic models, enums, paths, and other common types produce valid
    JSON instead of Python ``repr`` text, and the top-level and nested
    projections agree.

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
