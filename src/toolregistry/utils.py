import re
from typing import Literal, overload

import httpx


class HttpxClientConfig:
    def __init__(
        self,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        auth: tuple[str, str] | None = None,
        **extra_options,
    ):
        """
        Container for httpx client configuration.

        Args:
            base_url (str): The base URL for the API. This is required.
            headers (Optional[Dict[str, str]]): Custom request headers. Default is None.
            timeout (float): Request timeout in seconds. Default is 10.0.
            auth (Optional[Tuple[str, str]]): Basic authentication credentials (username, password). Default is None.
            extra_options (Any): Additional httpx client parameters.
        """
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.auth = auth
        self.extra_options = extra_options
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    @overload
    def to_client(self, use_async: Literal[False]) -> httpx.Client: ...

    @overload
    def to_client(self, use_async: Literal[True]) -> httpx.AsyncClient: ...

    def to_client(self, use_async: bool = False):
        """
        Creates an httpx client instance.

        Args:
            use_async (bool): Whether to create an asynchronous client. Default is False.

        Returns:
            Union[httpx.Client, httpx.AsyncClient]: An instance of httpx.Client or httpx.AsyncClient.
        """
        return self._make_client(use_async=use_async)

    def _make_client(self, use_async: bool = False):
        """Create a new httpx client instance.

        Args:
            use_async (bool): Whether to create an asynchronous client.

        Returns:
            Union[httpx.Client, httpx.AsyncClient]: A new client instance.
        """
        client_class = httpx.AsyncClient if use_async else httpx.Client
        return client_class(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            auth=self.auth,
            **self.extra_options,
        )

    @overload
    def get_persistent_client(
        self, use_async: Literal[False] = False
    ) -> httpx.Client: ...

    @overload
    def get_persistent_client(
        self, use_async: Literal[True] = ...
    ) -> httpx.AsyncClient: ...

    def get_persistent_client(self, use_async: bool = False):
        """Get or create a persistent client instance.

        Unlike ``to_client()``, this method reuses the same client across
        multiple calls, enabling HTTP connection pooling.

        Args:
            use_async (bool): Whether to return an async client.

        Returns:
            Union[httpx.Client, httpx.AsyncClient]: A persistent client instance.
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
