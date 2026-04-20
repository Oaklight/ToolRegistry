import asyncio
from typing import Any

from ...tool import Tool, ToolMetadata
from ...tool_registry import ToolRegistry
from ...tool_wrapper import BaseToolWrapper
from ...utils import HttpClientConfig, normalize_tool_name


class OpenAPIToolWrapper(BaseToolWrapper):
    """Wrapper class that provides both synchronous and asynchronous methods for OpenAPI tool calls.

    Args:
        client_config (HttpClientConfig): Configuration for the HTTP client.
        name (str): The name of the tool.
        method (str): The HTTP method (e.g., "get", "post").
        path (str): The API endpoint path.
        params (Optional[List[str]]): List of parameter names for the API call.
        persistent (bool): If True, reuse a persistent HTTP client.
    """

    def __init__(
        self,
        client_config: HttpClientConfig,
        name: str,
        method: str,
        path: str,
        params: list[str] | None,
        persistent: bool = True,
    ) -> None:
        super().__init__(name=name, params=params)
        self.client_config = client_config
        self.method = method.lower()
        self.path = path
        self._persistent = persistent

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronously call the API using the client configuration.

        Args:
            *args: Positional arguments for the API call.
            **kwargs: Keyword arguments for the API call.

        Returns:
            Any: The JSON response from the API.

        Raises:
            ValueError: If the tool name is not set.
            httpx.HTTPStatusError: If an HTTP error occurs.
        """
        kwargs = self._process_args(*args, **kwargs)

        if not self.name:
            raise ValueError("Tool name must be set before calling")

        if self._persistent:
            client = self.client_config.get_persistent_client(use_async=False)
            return self._do_sync_request(client, kwargs)
        else:
            with self.client_config.to_client(use_async=False) as client:
                return self._do_sync_request(client, kwargs)

    def _do_sync_request(self, client: Any, kwargs: dict[str, Any]) -> Any:
        """Execute the sync HTTP request."""
        if self.method == "get":
            response = client.get(self.path, params=kwargs)
        else:
            response = client.request(self.method, self.path, json=kwargs)
        response.raise_for_status()
        return response.json()

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronously call the API using the client configuration.

        Args:
            *args: Positional arguments for the API call.
            **kwargs: Keyword arguments for the API call.

        Returns:
            Any: The JSON response from the API.

        Raises:
            ValueError: If the tool name is not set.
            httpx.HTTPStatusError: If an HTTP error occurs.
        """
        kwargs = self._process_args(*args, **kwargs)

        if not self.name:
            raise ValueError("Tool name must be set before calling")

        if self._persistent:
            client = self.client_config.get_persistent_client(use_async=True)
            return await self._do_async_request(client, kwargs)
        else:
            async with self.client_config.to_client(use_async=True) as client:
                return await self._do_async_request(client, kwargs)

    async def _do_async_request(self, client: Any, kwargs: dict[str, Any]) -> Any:
        """Execute the async HTTP request."""
        if self.method == "get":
            response = await client.get(self.path, params=kwargs)
        else:
            response = await client.request(self.method, self.path, json=kwargs)
        response.raise_for_status()
        return response.json()


class OpenAPITool(Tool):
    """Wrapper class for OpenAPI tools preserving function metadata."""

    @classmethod
    def from_openapi_spec(
        cls,
        client_config: HttpClientConfig,
        path: str,
        method: str,
        spec: dict[str, Any],
        namespace: str | None = None,
        persistent: bool = True,
    ) -> "OpenAPITool":
        """Create an OpenAPITool instance from an OpenAPI specification.

        Args:
            client_config (HttpClientConfig): Configuration for HTTP client.
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

        parameters: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        param_names: list[str] = []

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
            client_config=client_config,
            name=func_name,
            method=method,
            path=path,
            params=param_names,
            persistent=persistent,
        )

        # Build source_detail from the base URL and endpoint path.
        source_detail = f"{client_config.base_url}{path}"

        tool = cls(
            name=func_name,
            description=description,
            parameters=parameters,
            callable=wrapper,
            metadata=ToolMetadata(
                is_async=False,
                source="openapi",
                source_detail=source_detail,
            ),
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
        self._client_configs: list[HttpClientConfig] = []

    async def register_openapi_tools_async(
        self,
        client_config: HttpClientConfig,
        openapi_spec: dict[str, Any],
        namespace: bool | str = False,
        persistent: bool = True,
    ) -> None:
        """Asynchronously register all tools defined in an OpenAPI specification.

        Args:
            client_config (HttpClientConfig): Configuration for the HTTP client.
            openapi_spec (Dict[str, Any]): The OpenAPI specification dictionary.
            namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If ``False``, no namespace is used.
                - If ``True``, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            persistent (bool): If True (default), reuse a persistent HTTP
                client for connection pooling.

        Returns:
            None
        """
        try:
            self._client_configs.append(client_config)

            resolved_ns = (
                namespace
                if isinstance(namespace, str)
                else openapi_spec.get("info", {}).get("title", "OpenAPI service")
                if namespace
                else None
            )

            # Process paths sequentially
            for path, methods in openapi_spec.get("paths", {}).items():
                for method, spec in methods.items():
                    if method.lower() not in ["get", "post", "put", "delete"]:
                        continue

                    open_api_tool = OpenAPITool.from_openapi_spec(
                        client_config=client_config,
                        path=path,
                        method=method,
                        spec=spec,
                        namespace=resolved_ns,
                        persistent=persistent,
                    )
                    self.registry.register(open_api_tool, namespace=resolved_ns)
        except Exception as e:
            raise ValueError(f"Failed to register OpenAPI tools: {e}")

    def register_openapi_tools(
        self,
        client_config: HttpClientConfig,
        openapi_spec: dict[str, Any],
        namespace: bool | str = False,
        persistent: bool = True,
    ) -> None:
        """Synchronously register all tools defined in an OpenAPI specification.

        Args:
            client_config (HttpClientConfig): Configuration for the HTTP client.
            openapi_spec (Dict[str, Any]): The OpenAPI specification dictionary.
            namespace (Union[bool, str]): Whether to prefix tool names with a namespace.
                - If ``False``, no namespace is used.
                - If ``True``, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            persistent (bool): If True (default), reuse a persistent HTTP
                client for connection pooling.

        Returns:
            None
        """
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.register_openapi_tools_async(
                    client_config, openapi_spec, namespace, persistent
                )
            )
        finally:
            if loop is not None:
                loop.close()

    def close(self) -> None:
        """Close all persistent HTTP clients (sync)."""
        for config in self._client_configs:
            config.close()

    async def close_async(self) -> None:
        """Close all persistent HTTP clients (async)."""
        for config in self._client_configs:
            await config.close_async()
        self._client_configs.clear()
