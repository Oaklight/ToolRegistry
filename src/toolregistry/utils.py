import re
from typing import Dict, Literal, Optional, Tuple, overload

import httpx


class HttpxClientConfig:
    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
        auth: Optional[Tuple[str, str]] = None,
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
        client_class = httpx.AsyncClient if use_async else httpx.Client
        return client_class(
            base_url=self.base_url,
            headers=self.headers,
            timeout=self.timeout,
            auth=self.auth,
            **self.extra_options,
        )


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
