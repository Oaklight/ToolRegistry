"""HTTP client configuration and base-URL handling.

The OpenAPI integration, the admin panel's source registration and any
caller that needs a base-URL client share this machinery.  It is not
OpenAPI-specific, so it lives next to the other internal helpers rather than
inside ``integrations/openapi``.

Every name here is re-exported from :mod:`toolregistry.utils`, which is the
documented compatibility surface.
"""

from __future__ import annotations

import re
import warnings
from typing import Any, Literal, overload
from urllib.parse import urlparse

from ._netpolicy import validate_outbound_url, validate_outbound_url_async
from ._vendor.httpclient import AsyncClient, Client

__all__ = [
    "DEFAULT_MAX_TOOL_RESPONSE_BYTES",
    "HttpClientConfig",
    "HttpxClientConfig",
    "OpenAPIPathError",
    "redact_url_userinfo",
]


#: ``scheme://user:password@`` in a URL, inside arbitrary text.  ``[^/\s]+``
#: is greedy and the trailing ``@`` is required, so the match ends at the
#: last ``@`` in the authority — the same split ``urlparse`` uses.  A ``@``
#: in the path does not match because the character class excludes ``/``.
_URL_USERINFO_SCHEME = re.compile(r"\b([A-Za-z][A-Za-z0-9+.\-]*://)[^/\s]+@")

#: ``//user:password@`` — a protocol-relative reference.  A password and a
#: token boundary are both required, so a path such as ``a//b@c`` and a
#: plain ``//host`` are left alone.
_URL_USERINFO_NETLOC = re.compile(r"(?<![:/\w.])(//)[^/\s:@]+:[^/\s@]+@")

#: ``user:password@host`` with no scheme.  The colon keeps an email address
#: (``user@host``) untouched; the greedy class consumes an ``@`` inside the
#: password up to the last one in the segment, as the scheme form does.
_URL_USERINFO_BARE = re.compile(r"(?<![:/\w.@])[^/\s:@]+:[^/\s]+@")


def redact_url_userinfo(text: str) -> str:
    """Remove ``user:password@`` userinfo from every URL in *text*.

    Error messages may quote a URL that a caller supplied.  A URL can carry
    credentials in its userinfo component, so strip them before the message
    reaches the caller or a log.  Three forms are handled: with a scheme,
    protocol-relative (``//user:password@host``) and without a scheme
    (``user:password@host``).  A bare email address is left alone.

    This lives in the shared module because the OpenAPI, admin and MCP
    integrations all need it.

    Args:
        text: Arbitrary text, such as an exception message.

    Returns:
        *text* with each URL's userinfo removed.
    """
    text = _URL_USERINFO_SCHEME.sub(r"\1", text)
    text = _URL_USERINFO_NETLOC.sub(r"\1", text)
    return _URL_USERINFO_BARE.sub("", text)


class OpenAPIPathError(ValueError):
    """A request path would leave the configured base origin.

    Raised before a tool is built or a request is sent.  It subclasses
    ``ValueError`` so existing callers keep working; the admin layer catches
    this type specifically so a path rejection is reported as a bad request
    instead of being confused with an internal fault.
    """


def _join_base_url_path(base_url: str, path: str) -> str:
    """Join *path* to *base_url* without allowing the origin to change.

    The clients carry credentials (``Authorization``, Basic auth) and custom
    headers.  An absolute URL — or a scheme-relative ``//host`` reference —
    would send them to a different origin, so only a path rooted at a single
    ``/`` is accepted, and the joined URL is checked against the base origin
    as a second line of defence.  A backslash is refused as well: some
    clients and proxies normalise it to ``/``, which would turn
    ``/\\host`` into a protocol-relative URL.

    This is the synchronous half of :func:`_join_base_url`: it does no name
    resolution, so an async client can call it on the event loop and then
    await the address check itself.

    Args:
        base_url: The configured base URL.
        path: The request path supplied by the caller.

    Returns:
        ``base_url + path``.

    Raises:
        OpenAPIPathError: If *path* is not a string rooted at a single ``/``,
            contains a backslash, or the joined URL's scheme or netloc differs
            from the base URL's.
    """
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or "\\" in path
    ):
        raise OpenAPIPathError(
            "Refusing to send a request for a non-relative path "
            f"{redact_url_userinfo(repr(path))}; only '/'-rooted paths "
            "without a backslash are allowed"
        )
    url = base_url + path
    base = urlparse(base_url)
    target = urlparse(url)
    if (base.scheme.lower(), base.netloc.lower()) != (
        target.scheme.lower(),
        target.netloc.lower(),
    ):
        raise OpenAPIPathError(
            "Refusing to send a request outside the configured base origin: "
            f"{redact_url_userinfo(url)!r}"
        )
    return url


def _join_base_url(
    base_url: str,
    path: str,
    *,
    allow_private_hosts: bool = False,
) -> str:
    """Join *path* to *base_url* and check the base address synchronously.

    Args:
        base_url: The configured base URL.
        path: The request path supplied by the caller.
        allow_private_hosts: Permit a base URL that resolves to a loopback,
            link-local or private address.  Defaults to ``False``; a client
            serving a local API passes ``True``.

    Returns:
        ``base_url + path``.

    Raises:
        OpenAPIPathError: If *path* is not a string rooted at a single ``/``,
            contains a backslash, or the joined URL's scheme or netloc differs
            from the base URL's.
        UnsafeAddressError: If *base_url* uses a scheme the outbound policy
            does not accept, names no host, does not resolve, or resolves to
            a non-public address while *allow_private_hosts* is false.
    """
    url = _join_base_url_path(base_url, path)
    # The origin cannot change from here, so checking the base once per
    # call (a cached decision) bounds every request this client makes.
    validate_outbound_url(base_url, allow_private_hosts=allow_private_hosts)
    return url


class _BaseUrlClient:
    """Sync HTTP client wrapper that prepends base_url to relative URLs."""

    def __init__(
        self,
        client: Client,
        base_url: str,
        *,
        allow_private_hosts: bool = False,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._allow_private_hosts = allow_private_hosts

    def _url(self, path: str) -> str:
        return _join_base_url(
            self._base_url,
            path,
            allow_private_hosts=self._allow_private_hosts,
        )

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

    def __enter__(self) -> _BaseUrlClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class _BaseUrlAsyncClient:
    """Async HTTP client wrapper that prepends base_url to relative URLs."""

    def __init__(
        self,
        client: AsyncClient,
        base_url: str,
        *,
        allow_private_hosts: bool = False,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._allow_private_hosts = allow_private_hosts

    async def _url(self, path: str) -> str:
        """Return the request URL after an awaited outbound address check.

        The path and origin checks are synchronous and cheap.  Name
        resolution is not: it is awaited through the event loop so a cache
        miss cannot stall the other tasks sharing the loop.
        """
        url = _join_base_url_path(self._base_url, path)
        await validate_outbound_url_async(
            self._base_url,
            allow_private_hosts=self._allow_private_hosts,
        )
        return url

    async def get(self, url: str, **kwargs: Any) -> Any:
        return await self._client.get(await self._url(url), **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        return await self._client.request(method, await self._url(url), **kwargs)

    async def post(self, url: str, **kwargs: Any) -> Any:
        return await self._client.post(await self._url(url), **kwargs)

    async def put(self, url: str, **kwargs: Any) -> Any:
        return await self._client.put(await self._url(url), **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> Any:
        return await self._client.patch(await self._url(url), **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> Any:
        return await self._client.delete(await self._url(url), **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> _BaseUrlAsyncClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()


#: Default cap on a buffered tool-call response, in bytes.  It matches the
#: OpenAPI document-download budget (``DEFAULT_MAX_SPEC_BYTES``): a tool that
#: answers with more than 10 MiB is almost always a misconfiguration, and the
#: whole body would otherwise be buffered in memory.  Callers that legitimately
#: need more raise this value; ``None`` disables the cap.
DEFAULT_MAX_TOOL_RESPONSE_BYTES = 10 * 1024 * 1024


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
        allow_private_hosts: Permit *base_url* to resolve to a loopback,
            link-local or private address.  Defaults to ``False``; set it for
            an API that runs on the same host or on a private network.
        **extra_options: Additional client parameters (e.g. verify, proxy,
            pool_size, max_response_size).  ``max_response_size`` defaults to
            :data:`DEFAULT_MAX_TOOL_RESPONSE_BYTES` (10 MiB); pass ``None`` to
            disable the cap.
    """

    # Known parameters that map directly to Client/AsyncClient constructor
    _KNOWN_CLIENT_PARAMS = {
        "verify",
        "proxy",
        "pool_size",
        "max_redirects",
        "max_response_size",
    }

    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        auth: tuple[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        allow_private_hosts: bool = False,
        **extra_options: Any,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.auth = auth
        self.cookies = cookies
        self.allow_private_hosts = allow_private_hosts
        # A buffered tool response is capped by default; ``None`` disables it.
        # Keep extra_options untouched: it is part of the public state (and
        # pickled with the config), so the default is resolved here instead.
        self.max_response_size = extra_options.get(
            "max_response_size", DEFAULT_MAX_TOOL_RESPONSE_BYTES
        )
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
            "max_response_size": self.max_response_size,
        }
        for key in self._KNOWN_CLIENT_PARAMS:
            if key in self.extra_options:
                kwargs[key] = self.extra_options[key]
        return kwargs

    def ensure_base_url_allowed(self) -> None:
        """Validate :attr:`base_url` on the calling thread.

        Callers that build a client from a URL they did not choose can run
        this ahead of time.  The decision is cached, so repeating it is cheap.

        Raises:
            UnsafeAddressError: If the base URL uses a scheme the outbound
                policy does not accept, names no host, does not resolve, or
                resolves to a non-public address while
                :attr:`allow_private_hosts` is false.
        """
        validate_outbound_url(
            self.base_url,
            allow_private_hosts=self.allow_private_hosts,
        )

    async def ensure_base_url_allowed_async(self) -> None:
        """Validate :attr:`base_url` without blocking the event loop.

        Raises:
            UnsafeAddressError: If the base URL uses a scheme the outbound
                policy does not accept, names no host, does not resolve,
                resolution times out, or resolves to a non-public address
                while :attr:`allow_private_hosts` is false.
        """
        await validate_outbound_url_async(
            self.base_url,
            allow_private_hosts=self.allow_private_hosts,
        )

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
            return _BaseUrlAsyncClient(
                raw,
                self.base_url,
                allow_private_hosts=self.allow_private_hosts,
            )
        else:
            raw = Client(**kwargs)
            return _BaseUrlClient(
                raw,
                self.base_url,
                allow_private_hosts=self.allow_private_hosts,
            )

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
            "allow_private_hosts": self.allow_private_hosts,
            "max_response_size": self.max_response_size,
            "extra_options": self.extra_options,
        }

    def __setstate__(self, state: dict) -> None:
        """Restore config; clients will be created lazily on first use."""
        self.base_url = state["base_url"]
        self.headers = state["headers"]
        self.timeout = state["timeout"]
        self.auth = state["auth"]
        self.cookies = state.get("cookies")
        self.allow_private_hosts = state.get("allow_private_hosts", False)
        # Default for a config pickled before the cap existed.
        self.max_response_size = state.get(
            "max_response_size", DEFAULT_MAX_TOOL_RESPONSE_BYTES
        )
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
