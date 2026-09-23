"""Tests for schema sanitization in get_schema() / get_schemas().

Verifies that Pydantic v2 artifacts (anyOf nullable patterns, 'nullable',
'title') are stripped from tool schemas before they reach LLM providers.

See: https://github.com/Oaklight/ToolRegistry/issues/215
"""

from __future__ import annotations

import typing

import pytest

from toolregistry import ToolRegistry
from toolregistry.tool import Tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_keys_recursive(schema: dict | list, target_keys: set[str]) -> list[str]:
    """Walk a nested dict/list and return all occurrences of *target_keys*."""
    found: list[str] = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in target_keys:
                found.append(key)
            found.extend(_collect_keys_recursive(value, target_keys))
    elif isinstance(schema, list):
        for item in schema:
            found.extend(_collect_keys_recursive(item, target_keys))
    return found


PYDANTIC_ARTIFACTS = {"title", "nullable"}


def _has_anyof_null(schema: dict | list) -> bool:
    """Return True if any anyOf contains a {type: null} branch."""
    if isinstance(schema, dict):
        any_of = schema.get("anyOf")
        if isinstance(any_of, list):
            for branch in any_of:
                if isinstance(branch, dict) and branch.get("type") == "null":
                    return True
        return any(_has_anyof_null(v) for v in schema.values())
    elif isinstance(schema, list):
        return any(_has_anyof_null(item) for item in schema)
    return False


# ---------------------------------------------------------------------------
# Test functions with various Optional / nullable patterns
# ---------------------------------------------------------------------------


def fn_optional_int(count: int | None = None) -> str:
    """A function with an optional int parameter."""
    return str(count)


def fn_optional_str(name: str | None = None) -> str:
    """A function with an optional str parameter."""
    return name or ""


def fn_multiple_optional(
    query: str,
    count: int | None = None,
    timeout: float | None = None,
    label: str | None = None,
) -> str:
    """A function with required + multiple optional parameters."""
    return query


def fn_nested_optional(
    data: dict | None = None,
    items: list | None = None,
) -> str:
    """A function with optional complex types."""
    return ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSchemaSanitization:
    """Verify that get_schema() strips Pydantic v2 artifacts."""

    def test_heterogeneous_union_preserves_all_non_null_branches(self):
        """Normalization must not narrow values accepted by the callable."""

        def fn(lat_spec: float | list[float] | None = None) -> None: ...

        prop = Tool.from_function(fn).parameters["properties"]["lat_spec"]
        key = "oneOf" if "oneOf" in prop else "anyOf"
        types = {branch.get("type") for branch in prop[key]}
        assert types == {"number", "array"}
        array = next(branch for branch in prop[key] if branch.get("type") == "array")
        assert array["items"]["type"] == "number"
        assert not _has_anyof_null(prop)

    def test_bare_tuple_scalar_list_union_has_wire_types(self):
        """The union from issue #269 should expose number and array types."""

        def fn(
            lat_spec: tuple | float | list[typing.Any] | None = None,
        ) -> None: ...

        prop = Tool.from_function(fn).parameters["properties"]["lat_spec"]
        key = "oneOf" if "oneOf" in prop else "anyOf"
        assert {branch.get("type") for branch in prop[key]} == {"number", "array"}

    def test_str_or_int_union_preserved(self):
        """Two-type union without None should preserve both branches."""

        def fn(x: str | int = "hello") -> None: ...

        prop = Tool.from_function(fn).parameters["properties"]["x"]
        key = "oneOf" if "oneOf" in prop else "anyOf"
        types = {v.get("type") for v in prop[key] if isinstance(v, dict)}
        assert types == {"string", "integer"}

    def test_single_nullable_still_collapses(self):
        """Simple T | None should still collapse to just T."""

        def fn(name: str | None = None) -> None: ...

        prop = Tool.from_function(fn).parameters["properties"]["name"]
        assert prop.get("type") == "string"
        assert "anyOf" not in prop
        assert "oneOf" not in prop

    @pytest.mark.xfail(
        reason="Requires llm-rosetta fix (Oaklight/llm-rosetta#747)",
        strict=False,
    )
    def test_get_schema_preserves_multi_union(self):
        """Multi-branch union must survive through get_schema() for all formats."""

        def fn(val: float | list[float] | None = None) -> None: ...

        tool = Tool.from_function(fn)
        for fmt in ("openai-chat", "anthropic"):
            schema = tool.get_schema(fmt)
            if fmt == "openai-chat":
                params = schema["function"]["parameters"]
            else:
                params = schema["input_schema"]
            val = params["properties"]["val"]
            assert "anyOf" in val or "oneOf" in val, (
                f"Union missing in {fmt} schema: {val}"
            )

    @pytest.mark.parametrize(
        "api_format", ["openai-chat", "anthropic", "gemini", "google-interactions"]
    )
    def test_no_title_in_schema(self, api_format: str):
        """title keys should be stripped from output schemas."""
        tool = Tool.from_function(fn_optional_int)
        schema = tool.get_schema(api_format)

        # Drill into the parameters/input_schema portion
        if api_format == "openai-chat":
            params = schema["function"]["parameters"]
        elif api_format == "anthropic":
            params = schema["input_schema"]
        elif api_format in ("gemini", "google-interactions"):
            params = schema.get("parameters", schema)
        else:
            params = schema

        found = _collect_keys_recursive(params, {"title"})
        assert not found, f"Found 'title' keys in {api_format} schema: {params}"

    @pytest.mark.parametrize(
        "api_format", ["openai-chat", "anthropic", "gemini", "google-interactions"]
    )
    def test_no_nullable_in_schema(self, api_format: str):
        """nullable keys should be stripped from output schemas."""
        tool = Tool.from_function(fn_multiple_optional)
        schema = tool.get_schema(api_format)

        if api_format == "openai-chat":
            params = schema["function"]["parameters"]
        elif api_format == "anthropic":
            params = schema["input_schema"]
        elif api_format in ("gemini", "google-interactions"):
            params = schema.get("parameters", schema)
        else:
            params = schema

        found = _collect_keys_recursive(params, {"nullable"})
        assert not found, f"Found 'nullable' keys in {api_format} schema: {params}"

    @pytest.mark.parametrize(
        "api_format", ["openai-chat", "anthropic", "gemini", "google-interactions"]
    )
    def test_no_anyof_null_in_schema(self, api_format: str):
        """anyOf with {type: null} branches should be collapsed."""
        tool = Tool.from_function(fn_multiple_optional)
        schema = tool.get_schema(api_format)

        if api_format == "openai-chat":
            params = schema["function"]["parameters"]
        elif api_format == "anthropic":
            params = schema["input_schema"]
        elif api_format in ("gemini", "google-interactions"):
            params = schema.get("parameters", schema)
        else:
            params = schema

        assert not _has_anyof_null(params), (
            f"Found anyOf with null branch in {api_format} schema: {params}"
        )

    def test_optional_int_resolves_to_integer_type(self):
        """Optional[int] should produce {type: integer}, not anyOf."""
        tool = Tool.from_function(fn_optional_int)
        schema = tool.get_schema("openai-chat")
        props = schema["function"]["parameters"]["properties"]

        count_schema = props["count"]
        assert count_schema.get("type") == "integer", (
            f"Expected type=integer for Optional[int], got: {count_schema}"
        )
        assert "anyOf" not in count_schema
        assert "nullable" not in count_schema

    def test_required_params_preserved(self):
        """Required parameters should still appear in the required list."""
        tool = Tool.from_function(fn_multiple_optional)
        schema = tool.get_schema("openai-chat")
        params = schema["function"]["parameters"]
        assert "query" in params.get("required", [])

    def test_registry_get_schemas_sanitized(self):
        """get_schemas() on a registry should also produce clean schemas."""
        registry = ToolRegistry()
        registry.register(Tool.from_function(fn_multiple_optional))
        schemas = registry.get_schemas(api_format="openai-chat")

        assert len(schemas) == 1
        params = schemas[0]["function"]["parameters"]

        found = _collect_keys_recursive(params, PYDANTIC_ARTIFACTS)
        assert not found, f"Found Pydantic artifacts in registry schemas: {found}"
        assert not _has_anyof_null(params)


class TestSchemaSanitizationMCPStyle:
    """Verify sanitization works for tools with raw parameter schemas (MCP/OpenAPI)."""

    def test_raw_anyof_nullable_cleaned(self):
        """A tool constructed with raw anyOf nullable schema should be sanitized."""
        raw_params = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "title": "Query"},
                "count": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                    "title": "Count",
                    "default": 5,
                },
                "timeout": {
                    "anyOf": [{"type": "number"}, {"type": "null"}],
                    "nullable": True,
                    "title": "Timeout",
                    "default": 30,
                },
            },
            "required": ["query"],
            "title": "SearchParams",
        }

        tool = Tool(
            name="search",
            description="Search things",
            parameters=raw_params,
            callable=lambda **kw: "ok",
        )
        schema = tool.get_schema("openai-chat")
        params = schema["function"]["parameters"]

        found = _collect_keys_recursive(params, PYDANTIC_ARTIFACTS)
        assert not found, f"Found artifacts: {found}, schema: {params}"
        assert not _has_anyof_null(params)

        # Verify the actual types resolved correctly
        props = params["properties"]
        assert props["count"].get("type") == "integer"
        assert props["timeout"].get("type") == "number"
        assert props["query"].get("type") == "string"

    def test_nested_anyof_cleaned(self):
        """anyOf nullable patterns in nested schemas should also be cleaned."""
        raw_params = {
            "type": "object",
            "title": "Params",
            "properties": {
                "config": {
                    "type": "object",
                    "title": "Config",
                    "properties": {
                        "retries": {
                            "anyOf": [{"type": "integer"}, {"type": "null"}],
                            "title": "Retries",
                            "default": 3,
                        },
                    },
                },
            },
        }

        tool = Tool(
            name="nested_tool",
            description="Tool with nested schema",
            parameters=raw_params,
            callable=lambda **kw: "ok",
        )
        schema = tool.get_schema("anthropic")
        params = schema["input_schema"]

        found = _collect_keys_recursive(params, PYDANTIC_ARTIFACTS)
        assert not found, f"Found artifacts in nested schema: {found}"
        assert not _has_anyof_null(params)


class TestSimplifyNullableNoNullableKey:
    """Verify _simplify_nullable_schemas no longer adds 'nullable' key."""

    def test_no_nullable_key_after_simplification(self):
        """_simplify_nullable_schemas should not add nullable: True."""
        from toolregistry.parameter_models import _simplify_nullable_schemas

        schema = {
            "type": "object",
            "properties": {
                "x": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": 5},
            },
        }
        result = _simplify_nullable_schemas(schema)
        prop = result["properties"]["x"]
        assert prop.get("type") == "integer"
        assert "nullable" not in prop
        assert "anyOf" not in prop
