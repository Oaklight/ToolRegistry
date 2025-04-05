import asyncio
import json
import os
import tempfile
from typing import Any, Callable, Dict, List, Optional

import httpx
import jsonref
import yaml
from prance import ResolvingParser
from prance.util.url import ResolutionError
from openapi_spec_validator import validate_spec_url
from pydantic import BaseModel

from .tool import Tool
from .tool_registry import ToolRegistry


def check_common_endpoints(url: str) -> Dict:
    """
    Check common endpoints to locate the OpenAPI schema.
    
    Args:
        url: Base URL of the web service.
    Returns:
        Dictionary with 'found': bool and, if found, 'schema_url'
    """
    common_endpoints = [
        '/openapi.json',
        '/swagger.json',
        '/api-docs',
        '/v3/api-docs',
        '/swagger.yaml',
        '/openapi.yaml'
    ]
    base_url = url.rstrip('/')
    with httpx.Client(timeout=5.0) as client:
        for endpoint in common_endpoints:
            full_url = f"{base_url}{endpoint}"
            try:
                response = client.get(full_url)
                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '').lower()
                    if 'json' in content_type or 'yaml' in content_type:
                        return {'found': True, 'schema_url': full_url}
            except Exception:
                continue
    return {'found': False}

def parse_openapi_spec_from_url(url: str) -> Dict:
    """
    Retrieve and parse OpenAPI specification from a URL.
    
    This function first attempts common endpoints to locate the schema.
    If that fails, it falls back to the original URL.
    
    Args:
        url: URL to OpenAPI spec (JSON/YAML)
    Returns:
        Parsed OpenAPI specification as a dictionary.
    Raises:
        ValueError: If unable to validate and parse the specification.
    """
    endpoint_result = check_common_endpoints(url)
    if endpoint_result.get("found"):
        schema_url = endpoint_result.get("schema_url")
        try:
            validate_spec_url(schema_url)
            parser = ResolvingParser(schema_url)
            return parser.specification
        except Exception as e:
            # Fallback to original URL if endpoint fails
            pass
    try:
        validate_spec_url(url)
        parser = ResolvingParser(url)
        return parser.specification
    except Exception as e:
        raise ValueError(f"Could not retrieve a valid OpenAPI spec from URL: {e}")

def get_openapi_spec(source: str) -> Dict:
    """Parse OpenAPI specification from file path or URL.

    Args:
        source: Path or URL to OpenAPI spec (JSON/YAML)
    Returns:
        Fully resolved OpenAPI specification
    Raises:
        FileNotFoundError: If local file not found
        ValueError: If parsing fails
        RuntimeError: For unexpected errors
    """
    try:
        # 1. If the source is a URL, use the dedicated HTTP parsing function
        if source.startswith("http"):
            return parse_openapi_spec_from_url(source)

        # 2. If the source is a local file, check if it exists
        if not os.path.exists(source):
            raise FileNotFoundError(f"File not found: {source}")

        with open(source, "r", encoding="utf-8") as file:
            content = file.read()

        # 3. Parse JSON files
        if source.endswith(".json"):
            parser = ResolvingParser(content)
            return parser.specification

        # 4. Parse YAML files
        if source.endswith((".yaml", ".yml")):
            parser = ResolvingParser(content)
            return parser.specification

    except (json.JSONDecodeError, yaml.YAMLError) as e:
        raise ValueError(f"Failed to parse OpenAPI specification: {e}")
    except ResolutionError as e:
        raise ValueError(f"Failed to resolve URL specification: {e}")
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred: {e}")


class OpenAPIToolWrapper:
    """Wrapper class providing both async and sync versions of OpenAPI tool calls."""

    def __init__(
        self,
        base_url: str,
        name: str,
        method: str,
        path: str,
        params: Optional[List[str]] = None,
    ) -> None:
        self.base_url = base_url
        self.name = name
        self.method = method.lower()
        self.path = path
        self.params = params or []

    def _process_args(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Process positional and keyword arguments.
        Maps positional args to parameter names and validates input.
        Returns processed kwargs.
        """
        if args:
            if not self.params:
                raise ValueError("Tool parameters not initialized")
            if len(args) > len(self.params):
                raise TypeError(
                    f"Expected at most {len(self.params)} positional arguments, got {len(args)}"
                )
            # Map positional args to their corresponding parameter names
            for i, arg in enumerate(args):
                param_name = self.params[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"Parameter '{param_name}' passed both as positional and keyword argument"
                    )
                kwargs[param_name] = arg
        return kwargs

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous implementation of OpenAPI tool call.
        Handles both positional and keyword arguments.
        Positional args are mapped to params in order, keyword args are passed directly.
        """
        kwargs = self._process_args(*args, **kwargs)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.call_async(**kwargs))

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Async implementation of OpenAPI tool call.
        Handles both positional and keyword arguments.
        Positional args are mapped to params in order, keyword args are passed directly.
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
        """Make the wrapper directly callable, using sync version by default."""
        try:
            # 尝试获取当前的 event loop
            asyncio.get_running_loop()
            # 如果成功，说明在异步环境中
            return self.call_async(*args, **kwargs)
        except RuntimeError:
            # 捕获异常，说明在同步环境中
            return self.call_sync(*args, **kwargs)


class OpenAPITool(Tool):
    """Wrapper class for OpenAPI tools that preserves original function metadata."""

    @classmethod
    def from_openapi_spec(
        cls,
        base_url: str,
        path: str,
        method: str,
        spec: Dict[str, Any],
    ) -> "OpenAPITool":
        """Create an OpenAPITool from OpenAPI specification."""
        operation_id = spec.get("operationId", f'{method}_{path.replace("/", "_")}')
        description = spec.get("description", spec.get("summary", ""))

        # Convert OpenAPI parameters to function parameters schema
        parameters = {"type": "object", "properties": {}, "required": []}
        param_names = []

        # Handle path/query parameters
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

        # Handle request body
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
            name=operation_id,
            method=method,
            path=path,
            params=param_names,
        )

        return cls(
            name=operation_id,
            description=description,
            parameters=parameters,
            callable=wrapper,
            is_async=False,
        )


class OpenAPIIntegration:
    """Handles integration with OpenAPI services for tool registration."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def register_openapi_tools_async(self, spec_source: str) -> None:
        """
        Async implementation to register all tools from an OpenAPI specification.

        Args:
            spec_source: Path or URL to OpenAPI spec (JSON/YAML)
        """
        openapi_spec = get_openapi_spec(spec_source)
        base_url = openapi_spec.get("servers", [{}])[0].get("url", "")

        for path, methods in openapi_spec.get("paths", {}).items():
            for method, spec in methods.items():
                if method.lower() not in ["get", "post", "put", "delete"]:
                    continue

                tool = OpenAPITool.from_openapi_spec(
                    base_url=base_url,
                    path=path,
                    method=method,
                    spec=spec,
                )
                self.registry.register(tool)

    def register_openapi_tools(self, spec_source: str) -> None:
        """
        Register all tools from an OpenAPI specification (synchronous entry point).

        Args:
            spec_source: Path or URL to OpenAPI spec (JSON/YAML)
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.register_openapi_tools_async(spec_source), loop
            )
            future.result()
        else:
            loop.run_until_complete(self.register_openapi_tools_async(spec_source))
