"""Unit tests for the ToolRegistry class."""

import json

import pytest

from toolregistry import Tool, ToolRegistry
from toolregistry.tool import ToolMetadata, ToolTag
from toolregistry.types import (
    ChatCompletionMessageFunctionToolCall,
    ResponseFunctionToolCall,
    Function,
)


class TestToolRegistry:
    """Test cases for the ToolRegistry class."""

    def test_registry_initialization_with_default_name(self):
        """Test ToolRegistry initialization with default name."""
        registry = ToolRegistry()

        assert registry.name.startswith("reg_")
        assert len(registry.name) == 8  # "reg_" + 4 hex chars
        assert len(registry._tools) == 0
        assert len(registry._sub_registries) == 0

    def test_registry_initialization_with_custom_name(self):
        """Test ToolRegistry initialization with custom name."""
        custom_name = "my_registry"
        registry = ToolRegistry(name=custom_name)

        assert registry.name == custom_name

    def test_contains_method(self, populated_registry):
        """Test __contains__ method for checking tool existence."""
        assert "add_numbers" in populated_registry
        assert "multiply_numbers" in populated_registry
        assert "nonexistent_tool" not in populated_registry

    def test_repr_and_str_methods(self, populated_registry):
        """Test __repr__ and __str__ methods return JSON."""
        repr_result = repr(populated_registry)
        str_result = str(populated_registry)

        assert repr_result == str_result
        # Should be valid JSON
        parsed = json.loads(repr_result)
        assert isinstance(parsed, list)
        assert len(parsed) >= 2  # At least 2 tools

    def test_getitem_method(self, populated_registry):
        """Test __getitem__ method for accessing callables."""
        add_func = populated_registry["add_numbers"]
        multiply_func = populated_registry["multiply_numbers"]
        nonexistent = populated_registry["nonexistent"]

        assert callable(add_func)
        assert callable(multiply_func)
        assert nonexistent is None

    def test_register_function(self, sample_registry):
        """Test registering a function."""

        def test_func(x: int) -> int:
            """Test function."""
            return x * 2

        sample_registry.register(test_func)

        assert "test_func" in sample_registry
        assert sample_registry.get_callable("test_func") == test_func

    def test_register_function_with_custom_name_and_description(self, sample_registry):
        """Test registering a function with custom name and description."""

        def test_func(x: int) -> int:
            return x * 2

        custom_name = "double"
        custom_description = "Double the input"

        sample_registry.register(
            test_func, name=custom_name, description=custom_description
        )

        assert custom_name in sample_registry
        tool = sample_registry.get_tool(custom_name)
        assert tool.description == custom_description

    def test_register_function_with_namespace(self, sample_registry):
        """Test registering a function with namespace."""

        def test_func(x: int) -> int:
            return x * 2

        namespace = "math"
        sample_registry.register(test_func, namespace=namespace)

        expected_name = f"{namespace}-test_func"
        assert expected_name in sample_registry
        assert namespace in sample_registry._sub_registries

    def test_register_tool_instance(self, sample_registry, sample_tool):
        """Test registering a Tool instance."""
        sample_registry.register(sample_tool)

        assert sample_tool.name in sample_registry
        assert sample_registry.get_tool(sample_tool.name) == sample_tool

    def test_register_tool_instance_with_namespace(self, sample_registry, sample_tool):
        """Test registering a Tool instance with namespace."""
        namespace = "math"
        original_name = sample_tool.name

        sample_registry.register(sample_tool, namespace=namespace)

        expected_name = f"{namespace}-{original_name}"
        assert expected_name in sample_registry
        assert sample_tool.name == expected_name

    def test_list_tools(self, populated_registry):
        """Test listing all tools."""
        tools = populated_registry.list_tools()

        assert isinstance(tools, list)
        assert "add_numbers" in tools
        assert "multiply_numbers" in tools
        assert len(tools) >= 2

    def test_get_available_tools_alias(self, populated_registry):
        """Test get_available_tools is an alias for list_tools."""
        tools1 = populated_registry.list_tools()
        tools2 = populated_registry.get_available_tools()

        assert tools1 == tools2

    def test_get_tools_json_all_tools(self, populated_registry):
        """Test getting JSON schema for all tools."""
        tools_json = populated_registry.get_tools_json()

        assert isinstance(tools_json, list)
        assert len(tools_json) >= 2

        for tool_schema in tools_json:
            assert "type" in tool_schema
            assert tool_schema["type"] == "function"
            assert "function" in tool_schema

    def test_get_tools_json_specific_tool(self, populated_registry):
        """Test getting JSON schema for a specific tool."""
        tools_json = populated_registry.get_tools_json(tool_name="add_numbers")

        assert isinstance(tools_json, list)
        assert len(tools_json) == 1
        assert tools_json[0]["function"]["name"] == "add_numbers"

    def test_get_tools_json_nonexistent_tool(self, populated_registry):
        """Test getting JSON schema for nonexistent tool returns empty list."""
        tools_json = populated_registry.get_tools_json(tool_name="nonexistent")

        assert tools_json == []

    def test_get_tools_json_different_api_formats(self, populated_registry):
        """Test getting JSON schema in different API formats."""
        openai_format = populated_registry.get_tools_json(api_format="openai")
        response_format = populated_registry.get_tools_json(
            api_format="openai-response"
        )

        assert len(openai_format) == len(response_format)

        # OpenAI format should have nested function
        assert "function" in openai_format[0]

        # Response format should have flat structure
        assert "name" in response_format[0]
        assert "strict" in response_format[0]

    def test_get_tools_json_anthropic_format(self, populated_registry):
        """Test getting JSON schema in Anthropic format."""
        anthropic_format = populated_registry.get_tools_json(api_format="anthropic")

        assert len(anthropic_format) >= 2
        assert "name" in anthropic_format[0]
        assert "input_schema" in anthropic_format[0]

    def test_get_tools_json_gemini_format(self, populated_registry):
        """Test getting JSON schema in Gemini format."""
        gemini_format = populated_registry.get_tools_json(api_format="gemini")

        assert len(gemini_format) >= 2
        assert "name" in gemini_format[0]
        assert "parameters" in gemini_format[0]

    def test_get_tool(self, populated_registry):
        """Test getting a tool by name."""
        tool = populated_registry.get_tool("add_numbers")

        assert isinstance(tool, Tool)
        assert tool.name == "add_numbers"

    def test_get_tool_nonexistent(self, populated_registry):
        """Test getting nonexistent tool returns None."""
        tool = populated_registry.get_tool("nonexistent")

        assert tool is None

    def test_get_callable(self, populated_registry):
        """Test getting callable by name."""
        callable_func = populated_registry.get_callable("add_numbers")

        assert callable(callable_func)
        result = callable_func(5, 3)
        assert result == 8

    def test_get_callable_nonexistent(self, populated_registry):
        """Test getting nonexistent callable returns None."""
        callable_func = populated_registry.get_callable("nonexistent")

        assert callable_func is None

    def test_set_execution_mode(self, sample_registry):
        """Test setting execution mode."""
        sample_registry.set_execution_mode("thread")
        assert sample_registry._execution_mode == "thread"

        sample_registry.set_execution_mode("process")
        assert sample_registry._execution_mode == "process"

    def test_set_execution_mode_invalid(self, sample_registry):
        """Test setting invalid execution mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid mode"):
            sample_registry.set_execution_mode("invalid")

    def test_execute_tool_calls_with_openai_format(self, populated_registry):
        """Test executing tool calls with OpenAI format."""
        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="add_numbers", arguments='{"a": 5, "b": 3}'),
            )
        ]

        results = populated_registry.execute_tool_calls(tool_calls)

        assert isinstance(results, dict)
        assert "call_1" in results
        assert int(results["call_1"]) == 8

    def test_execute_tool_calls_with_response_format(self, populated_registry):
        """Test executing tool calls with Response format."""
        tool_calls = [
            ResponseFunctionToolCall(
                call_id="call_2",
                name="multiply_numbers",
                arguments='{"x": 2.5, "y": 4.0}',
            )
        ]

        results = populated_registry.execute_tool_calls(tool_calls)

        assert isinstance(results, dict)
        assert "call_2" in results
        assert float(results["call_2"]) == 10.0

    def test_execute_tool_calls_with_execution_mode_override(self, populated_registry):
        """Test executing tool calls with execution mode override."""
        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_3",
                function=Function(name="add_numbers", arguments='{"a": 10, "b": 20}'),
            )
        ]

        results = populated_registry.execute_tool_calls(
            tool_calls, execution_mode="thread"
        )

        assert isinstance(results, dict)
        assert "call_3" in results
        assert int(results["call_3"]) == 30

    def test_recover_tool_call_assistant_message(self, populated_registry):
        """Test recovering assistant message from tool calls."""
        tool_calls = [
            ChatCompletionMessageFunctionToolCall(
                id="call_1",
                function=Function(name="add_numbers", arguments='{"a": 5, "b": 3}'),
            )
        ]

        tool_responses = {"call_1": "8"}

        messages = populated_registry.recover_tool_call_assistant_message(
            tool_calls, tool_responses
        )

        assert isinstance(messages, list)
        assert len(messages) == 2  # Assistant message + tool response

        # First message should be assistant with tool calls
        assert messages[0]["role"] == "assistant"
        assert "tool_calls" in messages[0]

        # Second message should be tool response
        assert messages[1]["role"] == "tool"
        assert messages[1]["content"] == "8"

    def test_merge_registries(self, sample_registry):
        """Test merging two registries."""
        # Create another registry with different tools
        other_registry = ToolRegistry(name="other")

        def subtract(a: int, b: int) -> int:
            return a - b

        def divide(a: float, b: float) -> float:
            return a / b

        other_registry.register(subtract)
        other_registry.register(divide)

        # Merge other into sample_registry
        sample_registry.merge(other_registry)

        # After merge, other's tools get prefixed with other's name
        assert "other-subtract" in sample_registry
        assert "other-divide" in sample_registry

    def test_merge_registries_invalid_type_raises_error(self, sample_registry):
        """Test merging with invalid type raises TypeError."""
        with pytest.raises(
            TypeError, match="Can only merge with another ToolRegistry instance"
        ):
            sample_registry.merge("not_a_registry")

    def test_update_sub_registries(self, sample_registry):
        """Test updating sub-registries based on tool names."""

        # Register tools with namespaces (which sets tool.namespace field)
        def add(a: int, b: int) -> int:
            return a + b

        def concat(a: str, b: str) -> str:
            return a + b

        sample_registry.register(add, namespace="math")
        sample_registry.register(concat, namespace="string")

        sample_registry._update_sub_registries()

        assert "math" in sample_registry._sub_registries
        assert "string" in sample_registry._sub_registries

    def test_prefix_tools_namespace(self, sample_registry):
        """Test prefixing tools with registry namespace."""

        def test_func(x: int) -> int:
            return x

        sample_registry.register(test_func)
        sample_registry._prefix_tools_namespace()

        expected_name = f"{sample_registry.name}-test_func"
        assert expected_name in sample_registry

    def test_prefix_tools_namespace_with_force(self, sample_registry):
        """Test prefixing tools with force=True."""

        def test_func(x: int) -> int:
            return x

        sample_registry.register(test_func, namespace="old")
        sample_registry._prefix_tools_namespace(force=True)

        expected_name = f"{sample_registry.name}-test_func"
        assert expected_name in sample_registry


class TestToolRegistryTagFiltering:
    """Test cases for tag-based filtering and stable sorting in get_tools_json."""

    @pytest.fixture()
    def tagged_registry(self):
        """Registry with tools tagged for filtering tests."""
        registry = ToolRegistry(name="tag_test")

        def read_file(path: str) -> str:
            """Read a file."""
            return path

        def delete_file(path: str) -> str:
            """Delete a file."""
            return path

        def fetch_url(url: str) -> str:
            """Fetch a URL."""
            return url

        def compute(x: int) -> int:
            """Pure computation."""
            return x * 2

        registry.register(
            Tool.from_function(
                read_file,
                metadata=ToolMetadata(tags={ToolTag.READ_ONLY, ToolTag.FILE_SYSTEM}),
            )
        )
        registry.register(
            Tool.from_function(
                delete_file,
                metadata=ToolMetadata(tags={ToolTag.DESTRUCTIVE, ToolTag.FILE_SYSTEM}),
            )
        )
        registry.register(
            Tool.from_function(
                fetch_url,
                metadata=ToolMetadata(
                    tags={ToolTag.NETWORK}, custom_tags={"api", "external"}
                ),
            )
        )
        registry.register(Tool.from_function(compute))
        return registry

    def test_get_tools_json_filter_by_tags(self, tagged_registry):
        """Test filtering tools by inclusion tags."""
        result = tagged_registry.get_tools_json(tags={ToolTag.FILE_SYSTEM})
        names = [t["function"]["name"] for t in result]

        assert len(names) == 2
        assert "read_file" in names
        assert "delete_file" in names
        assert "fetch_url" not in names
        assert "compute" not in names

    def test_get_tools_json_exclude_tags(self, tagged_registry):
        """Test excluding tools by tags."""
        result = tagged_registry.get_tools_json(exclude_tags={ToolTag.DESTRUCTIVE})
        names = [t["function"]["name"] for t in result]

        assert "delete_file" not in names
        assert "read_file" in names
        assert "fetch_url" in names
        assert "compute" in names

    def test_get_tools_json_tags_and_exclude_combined(self, tagged_registry):
        """Test combining inclusion and exclusion tags."""
        result = tagged_registry.get_tools_json(
            tags={ToolTag.FILE_SYSTEM},
            exclude_tags={ToolTag.DESTRUCTIVE},
        )
        names = [t["function"]["name"] for t in result]

        assert names == ["read_file"]

    def test_get_tools_json_tags_with_custom_tags(self, tagged_registry):
        """Test filtering with custom string tags."""
        result = tagged_registry.get_tools_json(tags={"api"})
        names = [t["function"]["name"] for t in result]

        assert names == ["fetch_url"]

    def test_get_tools_json_tags_no_match_returns_empty(self, tagged_registry):
        """Test that no matching tags returns empty list."""
        result = tagged_registry.get_tools_json(tags={"nonexistent_tag"})

        assert result == []

    def test_get_tools_json_stable_sort_default(self, tagged_registry):
        """Test that tools are sorted alphabetically by default."""
        result = tagged_registry.get_tools_json()
        names = [t["function"]["name"] for t in result]

        assert names == sorted(names)
        assert names == ["compute", "delete_file", "fetch_url", "read_file"]

    def test_get_tools_json_stable_sort_disabled(self, tagged_registry):
        """Test that sort=False preserves insertion order."""
        result = tagged_registry.get_tools_json(sort=False)
        names = [t["function"]["name"] for t in result]

        # Insertion order: read_file, delete_file, fetch_url, compute
        assert names == ["read_file", "delete_file", "fetch_url", "compute"]

    def test_get_tools_json_tags_ignored_when_tool_name_set(self, tagged_registry):
        """Test that tag filtering is skipped for single-tool lookup."""
        result = tagged_registry.get_tools_json(
            tool_name="compute",
            tags={ToolTag.NETWORK},
        )

        assert len(result) == 1
        assert result[0]["function"]["name"] == "compute"
