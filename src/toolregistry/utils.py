import re
import warnings
from typing import Any, Literal, overload

from ._vendor.httpclient import AsyncClient, Client


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
        **extra_options: Any,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.auth = auth
        self.extra_options = extra_options
        self._sync_client: _BaseUrlClient | None = None
        self._async_client: _BaseUrlAsyncClient | None = None

    def _client_kwargs(self) -> dict[str, Any]:
        """Build kwargs dict for Client/AsyncClient constructor."""
        kwargs: dict[str, Any] = {
            "headers": self.headers,
            "timeout": self.timeout,
            "auth": self.auth,
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
