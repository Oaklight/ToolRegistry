"""Tests for OpenAPI integration module."""

import json

import httpx
import pytest

from toolregistry import ToolRegistry
from toolregistry.openapi.integration import (
    OpenAPIIntegration,
    OpenAPITool,
    OpenAPIToolWrapper,
)
from toolregistry.openapi.utils import (
    determine_urls,
    extract_base_url_from_specs,
    load_openapi_spec,
    load_openapi_spec_async,
)
from toolregistry.utils import HttpxClientConfig


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


def _make_mock_transport(handler):
    """Create a mock transport from a handler function."""
    return httpx.MockTransport(handler)


def _make_config_with_mock(handler, base_url="http://test"):
    """Create an HttpxClientConfig backed by a mock transport."""
    transport = _make_mock_transport(handler)
    return HttpxClientConfig(
        base_url=base_url,
        transport=transport,
    )


# ===========================================================================
# TestOpenAPIToolWrapper
# ===========================================================================


class TestOpenAPIToolWrapper:
    """Tests for OpenAPIToolWrapper."""

    def test_call_sync_get(self):
        """GET request returns JSON."""

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            return httpx.Response(200, json={"pets": []})

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

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            body = json.loads(request.content)
            assert body["name"] == "Fido"
            return httpx.Response(201, json={"id": 1, "name": "Fido"})

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

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "PUT"
            return httpx.Response(200, json={"updated": True})

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

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "DELETE"
            return httpx.Response(200, json={"deleted": True})

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

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"async": True})

        transport = httpx.MockTransport(handler)
        config = HttpxClientConfig(base_url="http://test", transport=transport)
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

        async def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            return httpx.Response(201, json={"name": body["name"]})

        transport = httpx.MockTransport(handler)
        config = HttpxClientConfig(base_url="http://test", transport=transport)
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
        """HTTP error raises HTTPStatusError."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "not found"})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="show_pet",
            method="get",
            path="/pets/999",
            params=None,
            persistent=True,
        )
        with pytest.raises(httpx.HTTPStatusError):
            wrapper.call_sync()

    def test_call_sync_server_error(self):
        """500 error raises HTTPStatusError."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": "internal"})

        config = _make_config_with_mock(handler)
        wrapper = OpenAPIToolWrapper(
            client_config=config,
            name="list_pets",
            method="get",
            path="/pets",
            params=None,
            persistent=True,
        )
        with pytest.raises(httpx.HTTPStatusError):
            wrapper.call_sync()

    def test_call_sync_no_name_raises(self):
        """Calling with empty name raises ValueError."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={})

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

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

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

        def handler(request: httpx.Request) -> httpx.Response:
            captured["params"] = dict(request.url.params)
            return httpx.Response(200, json={"ok": True})

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

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=dict(request.url.params))

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
        config = HttpxClientConfig(base_url="http://test")
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
        # The tool may have injected params (e.g. 'thought' from think_augment)
        # but should have no user-defined params from the spec
        assert tool.parameters["required"] == []


# ===========================================================================
# TestOpenAPIIntegration
# ===========================================================================


class TestOpenAPIIntegration:
    """Tests for OpenAPIIntegration."""

    def test_register_tools_from_spec(self):
        """Registers all tools from an OpenAPI spec."""
        registry = ToolRegistry(name="test")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        config = HttpxClientConfig(
            base_url="http://test", transport=httpx.MockTransport(handler)
        )
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
        config = HttpxClientConfig(
            base_url="http://test",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC, namespace="pet_api")

        tool_names = [t.name for t in registry._tools.values()]
        assert all("pet_api" in name for name in tool_names)

    def test_register_with_namespace_true(self):
        """namespace=True derives from info.title."""
        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC, namespace=True)

        tool_names = [t.name for t in registry._tools.values()]
        # "Petstore" from info.title
        assert any("petstore" in name.lower() for name in tool_names)

    def test_register_with_namespace_false(self):
        """namespace=False means no prefix."""
        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
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
        config = HttpxClientConfig(
            base_url="http://test",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, spec)

        tool_names = [t.name for t in registry._tools.values()]
        assert "test_get" in tool_names
        assert "opts" not in tool_names
        assert "hd" not in tool_names

    def test_close_cleans_up(self):
        """close() clears client configs."""
        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)
        assert len(integration._client_configs) == 1
        integration.close()

    @pytest.mark.asyncio
    async def test_register_async(self):
        """Async registration works."""
        registry = ToolRegistry(name="test")

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        config = HttpxClientConfig(
            base_url="http://test", transport=httpx.MockTransport(handler)
        )
        integration = OpenAPIIntegration(registry)
        await integration.register_openapi_tools_async(config, PETSTORE_SPEC)

        tool_names = [t.name for t in registry._tools.values()]
        assert len(tool_names) == 5

    @pytest.mark.asyncio
    async def test_close_async(self):
        """Async close works."""
        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test",
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
        )
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

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/pets":
                return httpx.Response(200, json=[{"id": 1, "name": "Fido"}])
            return httpx.Response(404)

        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test", transport=httpx.MockTransport(handler)
        )
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)

        fn = registry.get_callable("list_pets")
        assert fn is not None
        result = fn(limit=10)
        assert isinstance(result, list)
        assert result[0]["name"] == "Fido"

    def test_register_and_call_post(self):
        """Register tools and call a POST tool through the registry."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path == "/pets":
                body = json.loads(request.content)
                return httpx.Response(201, json={"id": 2, "name": body["name"]})
            return httpx.Response(404)

        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test", transport=httpx.MockTransport(handler)
        )
        integration = OpenAPIIntegration(registry)
        integration.register_openapi_tools(config, PETSTORE_SPEC)

        fn = registry.get_callable("create_pet")
        assert fn is not None
        result = fn(name="Buddy")
        assert result["name"] == "Buddy"

    @pytest.mark.asyncio
    async def test_register_and_call_async(self):
        """Register tools and call asynchronously through the registry."""

        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[{"id": 1, "name": "Max"}])

        registry = ToolRegistry(name="test")
        config = HttpxClientConfig(
            base_url="http://test", transport=httpx.MockTransport(handler)
        )
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
        import yaml

        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.dump(PETSTORE_SPEC))
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
