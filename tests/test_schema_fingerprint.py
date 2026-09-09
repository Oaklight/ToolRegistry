"""Tests for schema fingerprint and staleness timestamp on ToolMetadata."""

from toolregistry import Tool, ToolMetadata, ToolRegistry
from toolregistry.utils import compute_schema_hash


# ---- compute_schema_hash ----


class TestComputeSchemaHash:
    def test_deterministic(self):
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        h1 = compute_schema_hash(schema)
        h2 = compute_schema_hash(schema)
        assert h1 == h2

    def test_key_order_invariant(self):
        s1 = {"type": "object", "properties": {"a": {"type": "string"}}}
        s2 = {"properties": {"a": {"type": "string"}}, "type": "object"}
        assert compute_schema_hash(s1) == compute_schema_hash(s2)

    def test_different_schemas_differ(self):
        s1 = {"type": "object", "properties": {"a": {"type": "string"}}}
        s2 = {"type": "object", "properties": {"a": {"type": "integer"}}}
        assert compute_schema_hash(s1) != compute_schema_hash(s2)

    def test_hex_length(self):
        h = compute_schema_hash({"type": "object"})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_empty_schema(self):
        h = compute_schema_hash({})
        assert len(h) == 64


# ---- ToolMetadata fields ----


class TestToolMetadataFields:
    def test_defaults(self):
        meta = ToolMetadata()
        assert meta.schema_hash == ""
        assert meta.last_refreshed_at == ""

    def test_schema_hash_set_explicitly(self):
        meta = ToolMetadata(schema_hash="abc123")
        assert meta.schema_hash == "abc123"

    def test_last_refreshed_at_set_explicitly(self):
        meta = ToolMetadata(last_refreshed_at="2025-01-01T00:00:00+00:00")
        assert meta.last_refreshed_at == "2025-01-01T00:00:00+00:00"

    def test_model_dump_includes_new_fields(self):
        meta = ToolMetadata(schema_hash="abc", last_refreshed_at="2025-01-01")
        d = meta.model_dump()
        assert d["schema_hash"] == "abc"
        assert d["last_refreshed_at"] == "2025-01-01"


# ---- Tool auto-populates schema_hash ----


class TestToolSchemaHash:
    def test_from_function_populates_hash(self):
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        tool = Tool.from_function(greet)
        assert tool.metadata.schema_hash
        assert len(tool.metadata.schema_hash) == 64

    def test_direct_construction_populates_hash(self):
        tool = Tool(
            name="test",
            description="test tool",
            parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
            callable=lambda: None,
        )
        assert tool.metadata.schema_hash
        assert len(tool.metadata.schema_hash) == 64

    def test_hash_matches_parameters(self):
        params = {"type": "object", "properties": {"x": {"type": "integer"}}}
        tool = Tool(
            name="test",
            description="test tool",
            parameters=params,
            callable=lambda: None,
        )
        # Note: Tool.__init__ may modify parameters (inject toolcall_reason),
        # so we hash the final parameters
        expected = compute_schema_hash(tool.parameters)
        assert tool.metadata.schema_hash == expected

    def test_different_params_different_hash(self):
        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        t1 = Tool.from_function(add)
        t2 = Tool.from_function(greet)
        assert t1.metadata.schema_hash != t2.metadata.schema_hash

    def test_pre_set_hash_not_overwritten(self):
        meta = ToolMetadata(schema_hash="custom_hash")
        tool = Tool(
            name="test",
            description="test tool",
            parameters={"type": "object", "properties": {}},
            callable=lambda: None,
            metadata=meta,
        )
        assert tool.metadata.schema_hash == "custom_hash"


# ---- Registry registration populates hash ----


class TestRegistrySchemaHash:
    def test_registered_tool_has_hash(self):
        registry = ToolRegistry()

        def hello(name: str) -> str:
            """Say hello."""
            return f"Hi, {name}!"

        registry.register(hello)
        tool = registry.get_tool("hello")
        assert tool is not None
        assert tool.metadata.schema_hash
        assert len(tool.metadata.schema_hash) == 64

    def test_last_refreshed_at_empty_after_registration(self):
        registry = ToolRegistry()

        def hello(name: str) -> str:
            """Say hello."""
            return f"Hi, {name}!"

        registry.register(hello)
        tool = registry.get_tool("hello")
        assert tool is not None
        assert tool.metadata.last_refreshed_at == ""


# ---- Refresh-path integration tests ----


class TestRefreshPathIntegration:
    """Verify schema_hash and last_refreshed_at are used/set during refresh."""

    def _make_openapi_spec(self, params: dict) -> dict:
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/greet": {
                    "get": {
                        "operationId": "greet",
                        "summary": "Say hello",
                        "parameters": [
                            {
                                "name": k,
                                "in": "query",
                                "required": v.get("required", False),
                                "schema": {"type": v["type"]},
                            }
                            for k, v in params.items()
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }

    def test_refresh_sets_last_refreshed_at(self):
        from toolregistry.utils import HttpClientConfig

        registry = ToolRegistry()
        spec_v1 = self._make_openapi_spec(
            {"name": {"type": "string", "required": True}}
        )
        client = HttpClientConfig(base_url="https://api.example.com")
        registry.register(client, source="openapi", openapi_spec=spec_v1)

        tool = registry.get_tool("greet")
        assert tool is not None
        assert tool.metadata.last_refreshed_at == ""

        result = registry.refresh_from_openapi(openapi_spec=spec_v1)
        assert result.unchanged == 1

        tool = registry.get_tool("greet")
        assert tool is not None
        assert tool.metadata.last_refreshed_at != ""

    def test_refresh_uses_schema_hash_for_diff(self):
        from toolregistry.utils import HttpClientConfig

        registry = ToolRegistry()
        spec_v1 = self._make_openapi_spec(
            {"name": {"type": "string", "required": True}}
        )
        client = HttpClientConfig(base_url="https://api.example.com")
        registry.register(client, source="openapi", openapi_spec=spec_v1)

        old_hash = registry.get_tool("greet").metadata.schema_hash
        assert old_hash

        spec_v2 = self._make_openapi_spec(
            {
                "name": {"type": "string", "required": True},
                "greeting": {"type": "string", "required": False},
            }
        )
        result = registry.refresh_from_openapi(openapi_spec=spec_v2)
        assert result.updated == ("greet",)

        new_hash = registry.get_tool("greet").metadata.schema_hash
        assert new_hash != old_hash
        assert registry.get_tool("greet").metadata.last_refreshed_at != ""
