import asyncio
from typing import Any, Dict, Literal, Optional, Tuple, overload
from urllib.parse import urlparse

import httpx
import jsonref  # type: ignore
import yaml  # type: ignore


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


def extract_base_url_from_specs(openapi_spec: Dict[str, Any]) -> Optional[str]:
    """
    Extract and validate the base URL from the 'servers' field of the OpenAPI specification.

    Args:
        openapi_spec (Dict[str, Any]): The parsed OpenAPI specification.

    Returns:
        Optional[str]: The validated base API URL extracted from the 'servers' field, or None if not valid.
    """
    servers = openapi_spec.get("servers", [])
    if servers:
        server_url = (
            servers[0].get("url", "").strip()
        )  # Get the first server URL and strip whitespace
        parsed_url = urlparse(server_url)

        # Validate the extracted URL
        if parsed_url.scheme in ["http", "https"] and parsed_url.netloc:
            return server_url.rstrip("/")

    return None


def determine_urls(url: str) -> Dict[str, Any]:
    """
    Determine whether the given URL or its common endpoints contain an OpenAPI schema.

    Args:
        url (str): Base URL or schema URL.

    Returns:
        Dict[str, Any]: Contains "found" (bool), "schema_url" (str) if valid or None, and "base_api_url" (str).
    """
    common_endpoints = [
        "/openapi.json",
        "/swagger.json",
        "/api-docs",
        "/v3/api-docs",
        "/swagger.yaml",
        "/openapi.yaml",
    ]
    base_url = url.rstrip("/")

    # Direct schema check for common endpoints
    for endpoint in common_endpoints:
        if base_url.endswith(endpoint):
            base_api_url = base_url.rstrip(endpoint)
            return {"found": True, "schema_url": base_url, "base_api_url": base_api_url}

    # Test appending endpoints to base URL
    with httpx.Client(timeout=5.0) as client:
        for endpoint in common_endpoints:
            full_url = f"{base_url}{endpoint}"
            try:
                response = client.get(full_url)
                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "").lower()
                    if "json" in content_type or "yaml" in content_type:
                        return {
                            "found": True,
                            "schema_url": full_url,
                            "base_api_url": base_url,
                        }
            except httpx.RequestError:
                continue

    return {"found": False, "base_api_url": base_url}


async def load_openapi_spec_async(uri: str) -> Dict[str, Any]:
    """Async version of load_openapi_spec using httpx.AsyncClient.

    Args:
        uri (str): URL or file path pointing to an OpenAPI specification.

    Returns:
        Dict[str, Any]: A dictionary containing the parsed OpenAPI specification.

    Raises:
        ValueError: If URI retrieval, parsing, or decoding fails.
    """
    try:
        parsed_uri = urlparse(uri)

        if parsed_uri.scheme in ("", "file"):  # Handle file paths
            file_path = parsed_uri.path if parsed_uri.scheme == "file" else uri
            with open(file_path, "rb") as file:
                openapi_spec_content = file.read()
        else:  # Handle URLs
            # First attempt to determine schema URL and fallback base URL
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(None, determine_urls, uri)
            uri = results["schema_url"] if results["found"] else uri

            # timeout for network requests (e.g., 10 seconds)
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(uri)
                response.raise_for_status()
                openapi_spec_content = response.content

        # Load and parse OpenAPI spec (CPU-bound operation)
        loop = asyncio.get_event_loop()
        openapi_spec_dict = await loop.run_in_executor(
            None, lambda: jsonref.replace_refs(yaml.safe_load(openapi_spec_content))
        )

        # Ensure return type matches Dict[str, Any]
        if not isinstance(openapi_spec_dict, dict):
            raise ValueError("OpenAPI spec must be a dictionary")
        return dict(openapi_spec_dict)  # Explicit type conversion

    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse OpenAPI content: {e}")
    except httpx.RequestError as e:
        raise ValueError(f"Network error when fetching URI: {e}")
    except httpx.HTTPStatusError as e:
        raise ValueError(
            f"HTTP error: {e.response.status_code} {e.response.reason_phrase}"
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Invalid file path: {e}")
    except Exception as e:
        raise ValueError(f"Unexpected error: {e}")


def load_openapi_spec(uri: str) -> Dict[str, Any]:
    """Sync version that calls the async implementation.

    Args:
        uri (str): URL or file path pointing to an OpenAPI specification.

    Returns:
        Dict[str, Any]: A dictionary containing the parsed OpenAPI specification.

    Raises:
        ValueError: If URI retrieval, parsing, or decoding fails."""
    return asyncio.run(load_openapi_spec_async(uri))
