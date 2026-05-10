"""Tests for OpenAPI integration module."""

import json
from urllib.parse import urlparse

import pytest

pytest.importorskip("jsonref")

from toolregistry import ToolRegistry  # noqa: E402
from toolregistry._vendor.httpclient import HTTPError, Response  # noqa: E402
from toolregistry.integrations.openapi.integration import (  # noqa: E402
    OpenAPIIntegration,
    OpenAPITool,
    OpenAPIToolWrapper,
)
from toolregistry.integrations.openapi.utils import (  # noqa: E402
    determine_urls,
    extract_base_url_from_specs,
    load_openapi_spec,
    load_openapi_spec_async,
)
from toolregistry.utils import HttpClientConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class _MockRequest:
    """Minimal request object for test handlers."""

    def __init__(self, method: str, url: str, content: bytes = b"", params=None):
        self.method = method
        self.content = content
        parsed = urlparse(url)
        self.url = _MockUrl(url, parsed.path, params or {})


class _MockUrl:
    """Minimal URL object for test handlers."""

    def __init__(self, full: str, path: str, params: dict):
        self._full = full
        self.path = path
        self.params = params

    def __str__(self):
        return self._full


def _mock_response(status_code: int, json_data=None, url: str = "") -> Response:
    """Create a zerodep Response mimicking httpx.Response(status_code, json=...)."""
    content = b""
    headers: dict[str, str] = {}
    if json_data is not None:
        content = json.dumps(json_data).encode()
        headers["content-type"] = "application/json"
    return Response(status_code, headers, content, url)


class _MockSyncClient:
    """Mock sync client that dispatches to a handler function."""

    def __init__(self, handler, base_url: str):
        self._handler = handler
        self._base_url = base_url

    def _resolve(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return self._base_url + path

    def _call(self, method: str, url: str, **kwargs) -> Response:
        full_url = self._resolve(url)
        content = b""
        if "json" in kwargs:
            content = json.dumps(kwargs["json"]).encode()
        params = {}
        if "params" in kwargs and kwargs["params"]:
            params = {k: str(v) for k, v in kwargs["params"].items()}
        req = _MockRequest(method, full_url, content, params)
        return self._handler(req)

    def get(self, url, **kwargs):
        return self._call("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self._call("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._call("DELETE", url, **kwargs)

    def request(self, method, url, **kwargs):
        return self._call(method.upper(), url, **kwargs)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _MockAsyncClient:
    """Mock async client that dispatches to a handler function."""

    def __init__(self, handler, base_url: str):
        self._handler = handler
        self._base_url = base_url

    def _resolve(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return self._base_url + path

    async def _call(self, method: str, url: str, **kwargs) -> Response:
        full_url = self._resolve(url)
        content = b""
        if "json" in kwargs:
            content = json.dumps(kwargs["json"]).encode()
        params = {}
        if "params" in kwargs and kwargs["params"]:
            params = {k: str(v) for k, v in kwargs["params"].items()}
        req = _MockRequest(method, full_url, content, params)
        return self._handler(req)

    async def get(self, url, **kwargs):
        return await self._call("GET", url, **kwargs)

    async def post(self, url, **kwargs):
        return await self._call("POST", url, **kwargs)

    async def put(self, url, **kwargs):
        return await self._call("PUT", url, **kwargs)

    async def delete(self, url, **kwargs):
        return await self._call("DELETE", url, **kwargs)

    async def request(self, method, url, **kwargs):
        return await self._call(method.upper(), url, **kwargs)

    async def aclose(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _MockHttpClientConfig(HttpClientConfig):
    """HttpClientConfig that returns mock clients using a handler function."""

    def __init__(self, handler, base_url="http://test"):
        super().__init__(base_url=base_url)
        self._handler = handler

    def _make_client(self, use_async=False):
        if use_async:
            return _MockAsyncClient(self._handler, self.base_url)
        return _MockSyncClient(self._handler, self.base_url)


def _make_config_with_mock(handler, base_url="http://test"):
    """Create an HttpClientConfig backed by a mock handler."""
    return _MockHttpClientConfig(handler, base_url=base_url)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PETSTORE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "servers": [{"url": "http://petstore.example.com/v1"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "How many items to return",
                    }
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Pet name",
                                    },
                                    "tag": {
                                        "type": "string",
                                        "description": "Pet tag",
                                    },
                                },
                                "required": ["name"],
                            }
                        }
                    }
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "showPetById",
                "summary": "Info for a specific pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The id of the pet to retrieve",
                    }
                ],
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
            },
            "put": {
                "operationId": "updatePet",
                "summary": "Update a pet",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "tag": {"type": "string"},
                                },
                            }
                        }
                    }
                },
            },
        },
    },
}


# ===========================================================================
# TestOpenAPIToolWrapper
# ===========================================================================


class TestOpenAPIToolWrapper:
    """Tests for OpenAPIToolWrapper."""

    def test_call_sync_get(self):
        """GET request returns JSON."""

        def handler(request):
            assert request.method == "GET"
            return _mock_response(200, {"pets": []})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=["limit"],
            persistent=True,
        )
        result = wrapper.call_sync(limit=10)
        assert result == {"pets": []}

    def test_call_sync_post(self):
        """POST request sends JSON body."""

        def handler(request):
            assert request.method == "POST"
            body = json.loads(request.content)
            assert body["name"] == "Fido"
            return _mock_response(201, {"id": 1, "name": "Fido"})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="create_pet",
            method="post",
            path="/pets",
            params=["name", "tag"],
            persistent=True,
        )
        result = wrapper.call_sync(name="Fido")
        assert result["id"] == 1

    def test_call_sync_put(self):
        """PUT request sends JSON body."""

        def handler(request):
            assert request.method == "PUT"
            return _mock_response(200, {"updated": True})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="update_pet",
            method="put",
            path="/pets/1",
            params=["name"],
            persistent=True,
        )
        result = wrapper.call_sync(name="Rex")
        assert result["updated"] is True

    def test_call_sync_delete(self):
        """DELETE request works."""

        def handler(request):
            assert request.method == "DELETE"
            return _mock_response(200, {"deleted": True})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="delete_pet",
            method="delete",
            path="/pets/1",
            params=None,
            persistent=True,
        )
        result = wrapper.call_sync()
        assert result["deleted"] is True

    @pytest.mark.asyncio
    async def test_call_async_get(self):
        """Async GET request works."""

        def handler(request):
            return _mock_response(200, {"async": True})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=["limit"],
            persistent=True,
        )
        result = await wrapper.call_async(limit=5)
        assert result["async"] is True

    @pytest.mark.asyncio
    async def test_call_async_post(self):
        """Async POST request sends JSON body."""

        def handler(request):
            body = json.loads(request.content)
            return _mock_response(201, {"name": body["name"]})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="create_pet",
            method="post",
            path="/pets",
            params=["name"],
            persistent=True,
        )
        result = await wrapper.call_async(name="Buddy")
        assert result["name"] == "Buddy"

    def test_call_sync_http_error(self):
        """HTTP error raises HTTPError."""

        def handler(request):
            return _mock_response(404, {"error": "not found"})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="show_pet",
            method="get",
            path="/pets/999",
            params=None,
            persistent=True,
        )
        with pytest.raises(HTTPError):
            wrapper.call_sync()

    def test_call_sync_server_error(self):
        """500 error raises HTTPError."""

        def handler(request):
            return _mock_response(500, {"error": "internal"})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=None,
            persistent=True,
        )
        with pytest.raises(HTTPError):
            wrapper.call_sync()

    def test_call_sync_no_name_raises(self):
        """Calling with empty name raises ValueError."""

        def handler(request):
            return _mock_response(200, {})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="",
            method="get",
            path="/pets",
            params=None,
            persistent=True,
        )
        with pytest.raises(ValueError, match="Tool name must be set"):
            wrapper.call_sync()

    def test_non_persistent_client(self):
        """Non-persistent mode creates a new client per call."""

        def handler(request):
            return _mock_response(200, {"ok": True})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=None,
            persistent=False,
        )
        result = wrapper.call_sync()
        assert result["ok"] is True

    def test_get_query_params_passed(self):
        """GET request passes kwargs as query params."""
        captured = {}

        def handler(request):
            captured["params"] = dict(request.url.params)
            return _mock_response(200, {"ok": True})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=["limit", "offset"],
            persistent=True,
        )
        wrapper.call_sync(limit=10, offset=20)
        assert captured["params"]["limit"] == "10"
        assert captured["params"]["offset"] == "20"

    def test_process_args_positional(self):
        """Positional args are mapped to param names."""
        captured = {}

        def handler(request):
            captured["params"] = dict(request.url.params)
            return _mock_response(200, captured["params"])

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=["limit", "offset"],
            persistent=True,
        )
        result = wrapper.call_sync(10, 20)
        assert result["limit"] == "10"


# ===========================================================================
# TestOpenAPITool
# ===========================================================================


class TestOpenAPITool:
    """Tests for OpenAPITool.from_openapi_spec()."""

    def _make_tool(self, path="/pets", method="get", spec=None, **kwargs):
        config = HttpClientConfig(base_url="http://test")
        if spec is None:
            spec = PETSTORE_SPEC["paths"]["/pets"]["get"]
        return OpenAPITool.from_openapi_spec(
            client_config=config,
            path=path,
            method=method,
            spec=spec,
            **kwargs,
        )

    def test_basic_get_tool(self):
        """Creates a tool from a GET operation."""
        tool = self._make_tool()
        assert tool.name == "list_pets"
        assert "List all pets" in tool.description

    def test_post_tool_with_request_body(self):
        """Creates a tool from a POST operation with requestBody."""
        spec = PETSTORE_SPEC["paths"]["/pets"]["post"]
        tool = self._make_tool(method="post", spec=spec)
        assert tool.name == "create_pet"
        assert "name" in tool.parameters["properties"]
        assert "tag" in tool.parameters["properties"]
        assert "name" in tool.parameters["required"]

    def test_tool_with_path_param(self):
        """Creates a tool with path parameters."""
        spec = PETSTORE_SPEC["paths"]["/pets/{petId}"]["get"]
        tool = self._make_tool(path="/pets/{petId}", spec=spec)
        assert tool.name == "show_pet_by_id"
        assert "petId" in tool.parameters["properties"]
        assert "petId" in tool.parameters["required"]

    def test_auto_naming_without_operation_id(self):
        """Generates name from method + path when operationId is missing."""
        spec = {"summary": "Do something", "parameters": []}
        tool = self._make_tool(path="/items/search", method="get", spec=spec)
        assert "get" in tool.name.lower() or "items" in tool.name.lower()

    def test_description_from_summary(self):
        """Uses summary when description is absent."""
        spec = {"operationId": "test_op", "summary": "A summary", "parameters": []}
        tool = self._make_tool(spec=spec)
        assert tool.description == "A summary"

    def test_description_from_description_field(self):
        """Prefers description over summary."""
        spec = {
            "operationId": "test_op",
            "summary": "A summary",
            "description": "Full description",
            "parameters": [],
        }
        tool = self._make_tool(spec=spec)
        assert tool.description == "Full description"

    def test_namespace_applied(self):
        """Namespace is applied to tool name."""
        tool = self._make_tool(namespace="petapi")
        assert "petapi" in tool.name

    def test_no_namespace(self):
        """Without namespace, tool name has no prefix."""
        tool = self._make_tool(namespace=None)
        assert tool.name == "list_pets"

    def test_put_with_params_and_body(self):
        """PUT with both path params and requestBody."""
        spec = PETSTORE_SPEC["paths"]["/pets/{petId}"]["put"]
        tool = self._make_tool(path="/pets/{petId}", method="put", spec=spec)
        props = tool.parameters["properties"]
        assert "petId" in props
        assert "name" in props

    def test_empty_parameters(self):
        """Operation with no parameters has no user-defined properties."""
        spec = {"operationId": "health_check", "parameters": []}
        tool = self._make_tool(spec=spec)
        assert tool.parameters["required"] == []


# ===========================================================================
# TestOpenAPIIntegration
# ===========================================================================


class TestOpenAPIIntegration:
    """Tests for OpenAPIIntegration."""

    def _ok_handler(self, request):
        return _mock_response(200, {"ok": True})

    def test_register_tools_from_spec(self):
        """Registers all tools from an OpenAPI spec."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)

        tool_names = [t.name for t in registry._tools.values()]
        assert "list_pets" in tool_names
        assert "create_pet" in tool_names
        assert "show_pet_by_id" in tool_names
        assert "delete_pet" in tool_names
        assert "update_pet" in tool_names

    def test_register_with_namespace_string(self):
        """Namespace string is applied to all tools."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC, namespace="pet_api")

        tool_names = [t.name for t in registry._tools.values()]
        assert all("pet_api" in name for name in tool_names)

    def test_register_with_namespace_true(self):
        """namespace=True derives from info.title."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC, namespace=True)

        tool_names = [t.name for t in registry._tools.values()]
        # "Petstore" from info.title
        assert any("petstore" in name.lower() for name in tool_names)

    def test_register_with_namespace_false(self):
        """namespace=False means no prefix."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC, namespace=False)

        tool_names = [t.name for t in registry._tools.values()]
        assert "list_pets" in tool_names

    def test_skips_non_http_methods(self):
        """Skips methods like 'options', 'head', 'parameters'."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/test": {
                    "options": {"operationId": "opts", "parameters": []},
                    "head": {"operationId": "hd", "parameters": []},
                    "get": {"operationId": "testGet", "parameters": []},
                }
            },
        }
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, spec)

        tool_names = [t.name for t in registry._tools.values()]
        assert "test_get" in tool_names
        assert "opts" not in tool_names
        assert "hd" not in tool_names

    def test_close_cleans_up(self):
        """close() clears client configs."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)
        assert len(integration._client_configs) == 1
        integration.close()

    @pytest.mark.asyncio
    async def test_register_async(self):
        """Async registration works."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        await integration.register_openapi_tools_async(config, PETSTORE_SPEC)

        tool_names = [t.name for t in registry._tools.values()]
        assert len(tool_names) == 5

    @pytest.mark.asyncio
    async def test_close_async(self):
        """Async close works."""
        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(self._ok_handler)
        integration = OpenAPIIntegration(registry)
        await integration.register_openapi_tools_async(config, PETSTORE_SPEC)
        await integration.close_async()
        assert len(integration._client_configs) == 0


# ===========================================================================
# TestOpenAPIToolEndToEnd
# ===========================================================================


class TestOpenAPIToolEndToEnd:
    """End-to-end: register from spec, then call through registry."""

    def test_register_and_call_get(self):
        """Register tools and call a GET tool through the registry."""

        def handler(request):
            if request.url.path == "/pets":
                return _mock_response(200, [{"id": 1, "name": "Fido"}])
            return _mock_response(404)

        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)

        fn = registry.get_callable("list_pets")
        assert fn is not None
        result = fn(limit=10)
        assert isinstance(result, list)
        assert result[0]["name"] == "Fido"

    def test_register_and_call_post(self):
        """Register tools and call a POST tool through the registry."""

        def handler(request):
            if request.method == "POST" and request.url.path == "/pets":
                body = json.loads(request.content)
                return _mock_response(201, {"id": 2, "name": body["name"]})
            return _mock_response(404)

        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(handler)
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)

        fn = registry.get_callable("create_pet")
        assert fn is not None
        result = fn(name="Buddy")
        assert result["name"] == "Buddy"

    @pytest.mark.asyncio
    async def test_register_and_call_async(self):
        """Register tools and call asynchronously through the registry."""

        def handler(request):
            return _mock_response(200, [{"id": 1, "name": "Max"}])

        registry = ToolRegistry(name="test")
        config = _make_config_with_mock(handler)
        integration = OpenAPIIntegration(registry)
        await integration.register_openapi_tools_async(config, PETSTORE_SPEC)

        fn = registry.get_callable("list_pets")
        assert fn is not None
        result = await fn.call_async(limit=5)
        assert result[0]["name"] == "Max"


# ===========================================================================
# TestOpenAPIUtils
# ===========================================================================


class TestExtractBaseUrl:
    """Tests for extract_base_url_from_specs()."""

    def test_valid_server_url(self):
        spec = {"servers": [{"url": "https://api.example.com/v1"}]}
        assert extract_base_url_from_specs(spec) == "https://api.example.com/v1"

    def test_strips_trailing_slash(self):
        spec = {"servers": [{"url": "https://api.example.com/"}]}
        assert extract_base_url_from_specs(spec) == "https://api.example.com"

    def test_no_servers(self):
        assert extract_base_url_from_specs({}) is None

    def test_empty_servers_list(self):
        assert extract_base_url_from_specs({"servers": []}) is None

    def test_relative_url(self):
        """Relative URL without scheme/netloc returns None."""
        spec = {"servers": [{"url": "/api/v1"}]}
        assert extract_base_url_from_specs(spec) is None

    def test_first_server_used(self):
        spec = {
            "servers": [
                {"url": "https://primary.example.com"},
                {"url": "https://secondary.example.com"},
            ]
        }
        assert extract_base_url_from_specs(spec) == "https://primary.example.com"


class TestDetermineUrls:
    """Tests for determine_urls()."""

    def test_direct_endpoint_match(self):
        """URL ending with known endpoint is recognized."""
        result = determine_urls("http://api.test/openapi.json")
        assert result["found"] is True
        assert result["schema_url"] == "http://api.test/openapi.json"

    def test_swagger_json_match(self):
        result = determine_urls("http://api.test/swagger.json")
        assert result["found"] is True

    def test_not_found_returns_base(self):
        """When no endpoint is found via probing, returns found=False."""
        # This will fail to connect since no server is running
        result = determine_urls("http://127.0.0.1:19999")
        assert result["found"] is False
        assert result["base_api_url"] == "http://127.0.0.1:19999"


class TestLoadOpenapiSpec:
    """Tests for load_openapi_spec() from file."""

    def test_load_from_json_file(self, tmp_path):
        """Load spec from a JSON file."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(PETSTORE_SPEC))
        result = load_openapi_spec(str(spec_file))
        assert result["info"]["title"] == "Petstore"

    def test_load_from_yaml_file(self, tmp_path):
        """Load spec from a YAML file."""
        from toolregistry._vendor.yaml import dump as yaml_dump

        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml_dump(PETSTORE_SPEC))
        result = load_openapi_spec(str(spec_file))
        assert result["info"]["title"] == "Petstore"

    def test_load_nonexistent_file(self):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_openapi_spec("/nonexistent/path/spec.json")

    @pytest.mark.asyncio
    async def test_load_async_from_file(self, tmp_path):
        """Async load from file path."""
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(PETSTORE_SPEC))
        result = await load_openapi_spec_async(str(spec_file))
        assert result["info"]["title"] == "Petstore"
