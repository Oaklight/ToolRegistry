import asyncio
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx
import jsonref  # type: ignore
import yaml  # type: ignore

from .tool import Tool
from .tool_registry import ToolRegistry
from .utils import normalize_tool_name


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


def load_openapi_spec(uri: str) -> Dict[str, Any]:
    """
    Fetch and decode the OpenAPI specification from the URI as a dictionary.

    Args:
        uri (str): URL or file path pointing to an OpenAPI specification.

    Returns:
        Dict[str, Any]: A dictionary containing the parsed OpenAPI specification and the base API URL (if applicable).

    Raises:
        ValueError: If URI retrieval, parsing, or decoding fails.
    """
    try:
        parsed_uri = urlparse(uri)

        if parsed_uri.scheme in ("", "file"):  # Handle file paths
            file_path = parsed_uri.path if parsed_uri.scheme == "file" else uri
            with open(file_path, "rb") as file:
                openapi_spec_content = file.read()
            base_url = None
        else:  # Handle URLs
            # First attempt to determine schema URL and fallback base URL
            results = determine_urls(uri)
            uri = results["schema_url"] if results["found"] else uri
            base_url = results["base_api_url"]

            with httpx.stream("GET", uri) as response:
                response.raise_for_status()
                openapi_spec_content = b"".join(response.iter_bytes())

        # Load and parse OpenAPI spec
        openapi_spec_dict = jsonref.replace_refs(yaml.safe_load(openapi_spec_content))

        # Refine the base_url using servers field if available and valid
        refined_base_url = extract_base_url_from_specs(openapi_spec_dict)
        if refined_base_url:
            base_url = refined_base_url  # Replace fallback base_url from determine_urls

        return {"spec": openapi_spec_dict, "base_url": base_url}

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


class OpenAPIToolWrapper:
    """Wrapper class that provides both synchronous and asynchronous methods for OpenAPI tool calls.

    Args:
        base_url (str): The base URL of the API.
        name (str): The name of the tool.
        method (str): The HTTP method (e.g. "get", "post").
        path (str): The API endpoint path.
        params (Optional[List[str]]): List of parameter names for the API call.
    """

    def __init__(
        self,
        base_url: str,
        name: str,
        method: str,
        path: str,
        params: Optional[List[str]],
    ) -> None:
        self.base_url = base_url
        self.name = name
        self.method = method.lower()
        self.path = path
        self.params = params

    def _process_args(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Map positional arguments to parameter names and validate input.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Dict[str, Any]: Processed keyword arguments with positional arguments mapped.

        Raises:
            ValueError: If the tool parameters are not initialized.
            TypeError: If too many positional arguments are provided or a parameter is passed twice.
        """
        if args:
            if not self.params:
                raise ValueError("Tool parameters not initialized")
            if len(args) > len(self.params):
                raise TypeError(
                    f"Expected at most {len(self.params)} positional arguments, got {len(args)}"
                )
            for i, arg in enumerate(args):
                param_name = self.params[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"Parameter '{param_name}' passed both as positional and keyword argument"
                    )
                kwargs[param_name] = arg
        return kwargs

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronously call the API using httpx.

        Args:
            *args: Positional arguments for the API call.
            **kwargs: Keyword arguments for the API call.

        Returns:
            Any: The JSON response from the API.

        Raises:
            ValueError: If the base URL or tool name is not set.
            httpx.HTTPStatusError: If an HTTP error occurs.
        """
        kwargs = self._process_args(*args, **kwargs)

        if not self.base_url or not self.name:
            raise ValueError("Base URL and name must be set before calling")

        with httpx.Client() as client:
            url = f"{self.base_url}{self.path}"
            if self.method == "get":
                response = client.get(url, params=kwargs)
            else:
                response = client.request(self.method, url, json=kwargs)
            response.raise_for_status()
            return response.json()

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronously call the API using httpx.

        Args:
            *args: Positional arguments for the API call.
            **kwargs: Keyword arguments for the API call.

        Returns:
            Any: The JSON response from the API.

        Raises:
            ValueError: If the base URL or tool name is not set.
            httpx.HTTPStatusError: If an HTTP error occurs.
        """
        kwargs = self._process_args(*args, **kwargs)

        if not self.base_url or not self.name:
            raise ValueError("Base URL and name must be set before calling")

        async with httpx.AsyncClient() as client:
            if self.method == "get":
                response = await client.get(
                    f"{self.base_url}{self.path}", params=kwargs
                )
            else:
                response = await client.request(
                    self.method, f"{self.base_url}{self.path}", json=kwargs
                )
            response.raise_for_status()
            return response.json()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the API call. Uses asynchronous call if in an async context,
        otherwise defaults to the synchronous version.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: The result of the API call.
        """
        try:
            asyncio.get_running_loop()
            return self.call_async(*args, **kwargs)
        except RuntimeError:
            return self.call_sync(*args, **kwargs)


class OpenAPITool(Tool):
    """Wrapper class for OpenAPI tools preserving function metadata."""

    @classmethod
    def from_openapi_spec(
        cls,
        base_url: str,
        path: str,
        method: str,
        spec: Dict[str, Any],
        namespace: Optional[str] = None,
    ) -> "OpenAPITool":
        """Create an OpenAPITool instance from an OpenAPI specification.

        Args:
            base_url (str): Base URL of the service.
            path (str): API endpoint path.
            method (str): HTTP method.
            spec (Dict[str, Any]): The OpenAPI operation specification.
            namespace (Optional[str]): Optional namespace to prefix tool names with.

        Returns:
            OpenAPITool: An instance of OpenAPITool configured for the specified operation.
        """
        operation_id = spec.get("operationId", f"{method}_{path.replace('/', '_')}")
        func_name = normalize_tool_name(operation_id)

        description = spec.get("description", spec.get("summary", ""))

        parameters: Dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        param_names: List[str] = []

        for param in spec.get("parameters", []):
            param_schema = param.get("schema", {})
            param_name = param["name"]
            parameters["properties"][param_name] = {
                "type": param_schema.get("type", "string"),
                "description": param.get("description", ""),
            }
            param_names.append(param_name)
            if param.get("required", False):
                parameters["required"].append(param_name)

        if "requestBody" in spec:
            content = spec["requestBody"].get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                for prop_name, prop_schema in schema.get("properties", {}).items():
                    parameters["properties"][prop_name] = {
                        "type": prop_schema.get("type", "string"),
                        "description": prop_schema.get("description", ""),
                    }
                    param_names.append(prop_name)
                if "required" in schema:
                    parameters["required"].extend(schema["required"])

        wrapper = OpenAPIToolWrapper(
            base_url=base_url,
            name=func_name,
            method=method,
            path=path,
            params=param_names,
        )

        tool = cls(
            name=func_name,
            description=description,
            parameters=parameters,
            callable=wrapper,
            is_async=False,
        )

        if namespace:
            tool.update_namespace(namespace)

        return tool


class OpenAPIIntegration:
    """Handles integration with OpenAPI services for tool registration.

    Attributes:
        registry (ToolRegistry): The tool registry where tools are registered.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry: ToolRegistry = registry

    async def register_openapi_tools_async(
        self,
        uri: str,
        base_url: Optional[str] = None,
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Asynchronously register all tools defined in an OpenAPI specification.

        Args:
            uri (str): File path or URL to the OpenAPI specification (JSON/YAML).
            base_url (Optional[str]): Base URL for API calls. If None, will be extracted from spec.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Returns:
            None
        """

        specs = load_openapi_spec(uri)
        openapi_spec = specs["spec"]
        base_url = specs["base_url"] or base_url

        if not base_url:
            raise ValueError(
                "base_url must be specified, either by argument or via OpenAPI spec"
            )

        if isinstance(with_namespace, str):
            namespace = with_namespace
        elif with_namespace:  # with_namespace is True
            namespace = openapi_spec.get("info", {}).get("title", "OpenAPI service")
        else:
            namespace = None

        for path, methods in openapi_spec.get("paths", {}).items():
            for method, spec in methods.items():
                if method.lower() not in ["get", "post", "put", "delete"]:
                    continue

                open_api_tool = OpenAPITool.from_openapi_spec(
                    base_url=base_url or "",
                    path=path,
                    method=method,
                    spec=spec,
                    namespace=namespace,
                )
                self.registry.register(open_api_tool, namespace=namespace)

    def register_openapi_tools(
        self,
        uri: str,
        base_url: Optional[str] = None,
        with_namespace: Union[bool, str] = False,
    ) -> None:
        """Asynchronously register all tools defined in an OpenAPI specification.

        Args:
            uri (str): File path or URL to the OpenAPI specification (JSON/YAML).
            base_url (Optional[str]): Base URL for API calls. If None, will be extracted from spec.
            with_namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If `False`, no namespace is used.
                - If `True`, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.

        Returns:
            None
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.register_openapi_tools_async(uri, base_url, with_namespace),
                loop,
            )
            future.result()
        else:
            loop.run_until_complete(
                self.register_openapi_tools_async(uri, base_url, with_namespace)
            )
