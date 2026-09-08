import logging
import threading
from typing import Any

from ...events import ChangeEvent, ChangeEventType, RefreshResult

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


def _copy_json_schema(schema: dict[str, Any], description: str = "") -> dict[str, Any]:
    """Copy a JSON Schema fragment and merge an OpenAPI description."""
    copied = dict(schema) if isinstance(schema, dict) else {}
    if "type" not in copied:
        copied["type"] = "string"
    if description and "description" not in copied:
        copied["description"] = description
    return copied


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
            parameters["properties"][param_name] = _copy_json_schema(
                param_schema,
                param.get("description", ""),
            )
            param_names.append(param_name)
            if param.get("required", False):
                parameters["required"].append(param_name)

        if "requestBody" in spec:
            content = spec["requestBody"].get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                for prop_name, prop_schema in schema.get("properties", {}).items():
                    parameters["properties"][prop_name] = _copy_json_schema(prop_schema)
                    param_names.append(prop_name)
                if "required" in schema:
                    parameters["required"].extend(schema["required"])

        if not parameters["required"]:
            parameters.pop("required")

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
                natural_backend="inline",
            ),
        )

        if namespace:
            tool.update_namespace(namespace)

        return tool


logger = logging.getLogger(__name__)


class OpenAPIIntegration:
    """Handles integration with OpenAPI services for tool registration.

    Attributes:
        registry (ToolRegistry): The tool registry where tools are registered.
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry: ToolRegistry = registry
        self._client_configs: list[HttpClientConfig] = []
        self._registered_tool_names: set[str] = set()
        self._spec_url: str | None = None
        self._client_config: HttpClientConfig | None = None
        self._resolved_ns: str | None = None
        self._persistent: bool = True
        self._openapi_spec: dict[str, Any] | None = None
        self._etag: str | None = None
        self._refresh_lock = threading.Lock()
        self._poll_timer: threading.Timer | None = None
        self._poll_interval: float | None = None

    async def register_openapi_tools_async(
        self,
        client_config: HttpClientConfig,
        openapi_spec: dict[str, Any],
        namespace: bool | str = False,
        persistent: bool = True,
        spec_url: str | None = None,
    ) -> None:
        """Asynchronously register all tools defined in an OpenAPI specification.

        Args:
            client_config: Configuration for the HTTP client.
            openapi_spec: The OpenAPI specification dictionary.
            namespace: Whether to prefix tool names with a namespace.
                - If ``False``, no namespace is used.
                - If ``True``, the namespace is derived from the OpenAPI info.title.
                - If a string is provided, it is used as the namespace.
                Defaults to False.
            persistent: If True (default), reuse a persistent HTTP client for
                connection pooling.
            spec_url: Optional URL where the spec was fetched from.  Stored for
                later ETag-based refresh via :meth:`refresh_async`.
        """
        try:
            self._client_configs.append(client_config)
            self._client_config = client_config
            self._persistent = persistent
            self._spec_url = spec_url
            self._openapi_spec = openapi_spec

            resolved_ns = (
                namespace
                if isinstance(namespace, str)
                else openapi_spec.get("info", {}).get("title", "OpenAPI service")
                if namespace
                else None
            )
            self._resolved_ns = resolved_ns

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
                    self._registered_tool_names.add(open_api_tool.name)
        except Exception as e:
            raise ValueError(f"Failed to register OpenAPI tools: {e}")

    def register_openapi_tools(
        self,
        client_config: HttpClientConfig,
        openapi_spec: dict[str, Any],
        namespace: bool | str = False,
        persistent: bool = True,
        spec_url: str | None = None,
    ) -> None:
        """Synchronously register all tools defined in an OpenAPI specification.

        Args:
            client_config: Configuration for the HTTP client.
            openapi_spec: The OpenAPI specification dictionary.
            namespace: Whether to prefix tool names with a namespace.
                Defaults to False.
            persistent: If True (default), reuse a persistent HTTP client for
                connection pooling.
            spec_url: Optional URL where the spec was fetched from.
        """
        from ..._async_runtime import AsyncRuntime

        AsyncRuntime.run_sync(
            self.register_openapi_tools_async(
                client_config, openapi_spec, namespace, persistent, spec_url
            )
        )

    # ---- Refresh ----

    async def _resolve_spec(
        self,
        openapi_spec: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, bool]:
        """Resolve the OpenAPI spec to use for refresh.

        Returns:
            ``(spec, skipped)`` — *spec* is ``None`` only when *skipped* is
            ``True`` (ETag 304).
        """
        if openapi_spec is not None:
            return openapi_spec, False

        if self._spec_url:
            from .utils import load_openapi_spec_conditional_async

            spec, new_etag = await load_openapi_spec_conditional_async(
                self._spec_url, self._etag
            )
            if spec is None:
                return None, True
            self._etag = new_etag
            return spec, False

        if self._openapi_spec is not None:
            return self._openapi_spec, False

        raise ValueError(
            "Cannot refresh: no spec_url was provided at registration "
            "time and no spec dict was passed to refresh()."
        )

    def _build_tool_map(
        self,
        openapi_spec: dict[str, Any],
        client_config: HttpClientConfig,
    ) -> dict[str, OpenAPITool]:
        """Build ``{name: OpenAPITool}`` from a parsed spec."""
        sep = getattr(self.registry, "_name_sep", "-")
        tools: dict[str, OpenAPITool] = {}
        for path, methods in openapi_spec.get("paths", {}).items():
            for method, spec in methods.items():
                if method.lower() not in ["get", "post", "put", "delete"]:
                    continue
                candidate = OpenAPITool.from_openapi_spec(
                    client_config=client_config,
                    path=path,
                    method=method,
                    spec=spec,
                    namespace=self._resolved_ns,
                    persistent=self._persistent,
                )
                candidate.update_namespace(self._resolved_ns, force=True, sep=sep)
                tools[candidate.name] = candidate
        return tools

    def _apply_diff(
        self,
        new_tools: dict[str, OpenAPITool],
    ) -> tuple[list[str], list[str], list[str], int]:
        """Diff *new_tools* against registered tools and apply changes.

        Returns:
            ``(added, removed, updated, unchanged)`` lists/count.
        """
        old_names = set(self._registered_tool_names)
        new_names = set(new_tools.keys())
        sep = getattr(self.registry, "_name_sep", "-")

        # Snapshot disabled state
        disabled_snapshot: dict[str, str] = {}
        for name in old_names:
            if not self.registry.is_enabled(name):
                disabled_snapshot[name] = self.registry.get_disable_reason(name) or ""

        added: list[str] = []
        removed: list[str] = []
        updated: list[str] = []
        unchanged = 0

        for name in old_names - new_names:
            self.registry._unregister(name)
            removed.append(name)

        for name in new_names - old_names:
            self.registry.register(new_tools[name], namespace=self._resolved_ns)
            added.append(name)

        for name in old_names & new_names:
            candidate = new_tools[name]
            existing = self.registry._tools.get(name)
            if existing and (
                existing.parameters != candidate.parameters
                or existing.description != candidate.description
            ):
                candidate.update_namespace(self._resolved_ns, force=True, sep=sep)
                self.registry._tools[name] = candidate
                self.registry._emit_change(
                    ChangeEvent(
                        event_type=ChangeEventType.REFRESH,
                        tool_name=name,
                    )
                )
                updated.append(name)
            else:
                unchanged += 1

        for name, reason in disabled_snapshot.items():
            if name in new_names:
                self.registry.disable(name, reason)

        self._registered_tool_names = new_names
        return added, removed, updated, unchanged

    async def refresh_async(
        self,
        openapi_spec: dict[str, Any] | None = None,
    ) -> RefreshResult:
        """Re-fetch the OpenAPI spec and synchronise registered tools.

        Args:
            openapi_spec: A pre-parsed spec dict.  When ``None``, the spec is
                re-fetched from :attr:`_spec_url` (with ETag support) or the
                last stored spec is reused.

        Returns:
            A :class:`RefreshResult` describing what changed.

        Raises:
            ValueError: If no spec can be obtained (no URL and no stored spec).
        """
        source_detail = self._spec_url or (
            self._client_config.base_url if self._client_config else ""
        )

        resolved, skipped = await self._resolve_spec(openapi_spec)
        if skipped:
            return RefreshResult(
                source="openapi", source_detail=source_detail, skipped=True
            )
        assert resolved is not None
        self._openapi_spec = resolved

        if self._client_config is None:
            raise ValueError(
                "Cannot refresh: no client config stored. "
                "Call register_openapi_tools() first."
            )

        new_tools = self._build_tool_map(resolved, self._client_config)
        added, removed, updated, unchanged = self._apply_diff(new_tools)

        return RefreshResult(
            source="openapi",
            source_detail=source_detail,
            added=tuple(added),
            removed=tuple(removed),
            updated=tuple(updated),
            unchanged=unchanged,
        )

    def refresh(
        self,
        openapi_spec: dict[str, Any] | None = None,
    ) -> RefreshResult:
        """Synchronous version of :meth:`refresh_async`."""
        from ..._async_runtime import AsyncRuntime

        return AsyncRuntime.run_sync(self.refresh_async(openapi_spec))

    # ---- Background polling ----

    def start_polling(self, interval: float) -> None:
        """Start periodic background refresh.

        Args:
            interval: Seconds between refresh attempts.
        """
        self.stop_polling()
        self._poll_interval = interval
        self._schedule_next_poll()

    def stop_polling(self) -> None:
        """Stop background polling if active."""
        self._poll_interval = None
        if self._poll_timer is not None:
            self._poll_timer.cancel()
            self._poll_timer = None

    def _schedule_next_poll(self) -> None:
        if self._poll_interval is None:
            return
        self._poll_timer = threading.Timer(self._poll_interval, self._poll_tick)
        self._poll_timer.daemon = True
        self._poll_timer.start()

    def _poll_tick(self) -> None:
        with self._refresh_lock:
            try:
                self.refresh()
            except Exception:
                logger.exception("OpenAPI refresh poll failed")
        self._schedule_next_poll()

    # ---- Lifecycle ----

    def close(self) -> None:
        """Close all persistent HTTP clients (sync)."""
        self.stop_polling()
        for config in self._client_configs:
            config.close()

    async def close_async(self) -> None:
        """Close all persistent HTTP clients (async)."""
        self.stop_polling()
        for config in self._client_configs:
            await config.close_async()
        self._client_configs.clear()
