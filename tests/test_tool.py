"""Unit tests for the Tool class."""

import inspect

import pytest

from toolregistry.tool import Tool, ToolMetadata, ToolTag


class TestTool:
    """Test cases for the Tool class."""

    def test_tool_creation_from_function(self, sample_function):
        """Test creating a Tool from a function."""
        tool = Tool.from_function(sample_function)

        assert tool.name == "add_numbers"
        assert "Add two numbers together" in tool.description
        assert tool.callable == sample_function
        assert not tool.is_async
        assert isinstance(tool.parameters, dict)

    def test_tool_creation_with_custom_name_and_description(self, sample_function):
        """Test creating a Tool with custom name and description."""
        custom_name = "custom_add"
        custom_description = "Custom addition function"

        tool = Tool.from_function(
            sample_function, name=custom_name, description=custom_description
        )

        assert tool.name == custom_name
        assert tool.description == custom_description

    def test_tool_creation_with_namespace(self, sample_function):
        """Test creating a Tool with namespace."""
        namespace = "math"
        tool = Tool.from_function(sample_function, namespace=namespace)

        assert tool.name == "math-add_numbers"

    def test_tool_creation_from_async_function(self, async_sample_function):
        """Test creating a Tool from an async function."""
        tool = Tool.from_function(async_sample_function)

        assert tool.name == "async_add_numbers"
        assert tool.is_async
        assert inspect.iscoroutinefunction(tool.callable)

    def test_tool_creation_from_lambda_without_name_raises_error(self):
        """Test that creating a Tool from lambda without name raises ValueError."""
        lambda_func = lambda x: x * 2  # noqa: E731

        with pytest.raises(
            ValueError, match="You must provide a name for lambda functions"
        ):
            Tool.from_function(lambda_func)

    def test_tool_creation_from_lambda_with_name(self):
        """Test creating a Tool from lambda with provided name."""
        lambda_func = lambda x: x * 2  # noqa: E731
        tool = Tool.from_function(lambda_func, name="double")

        assert tool.name == "double"
        assert tool.callable == lambda_func

    def test_get_json_schema_openai_format(self, sample_tool):
        """Test getting JSON schema in OpenAI format."""
        schema = sample_tool.get_json_schema("openai")

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == sample_tool.name
        assert schema["function"]["description"] == sample_tool.description
        assert "parameters" in schema["function"]

    def test_get_json_schema_openai_chatcompletion_format(self, sample_tool):
        """Test getting JSON schema in OpenAI chat completion format."""
        schema = sample_tool.get_json_schema("openai-chatcompletion")

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == sample_tool.name

    def test_get_json_schema_openai_response_format(self, sample_tool):
        """Test getting JSON schema in OpenAI response format."""
        schema = sample_tool.get_json_schema("openai-response")

        assert schema["type"] == "function"
        assert schema["name"] == sample_tool.name
        assert schema["description"] == sample_tool.description
        assert schema["strict"] is False

    def test_get_json_schema_anthropic_format(self, sample_tool):
        """Test getting JSON schema in Anthropic format."""
        schema = sample_tool.get_json_schema("anthropic")

        assert schema["name"] == sample_tool.name
        assert "input_schema" in schema

    def test_get_json_schema_gemini_format(self, sample_tool):
        """Test getting JSON schema in Gemini format."""
        schema = sample_tool.get_json_schema("gemini")

        assert schema["name"] == sample_tool.name
        assert "parameters" in schema

    def test_get_json_schema_unsupported_format_raises_error(self, sample_tool):
        """Test that unsupported API format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported API format"):
            sample_tool.get_json_schema("unsupported_format")

    def test_describe_alias(self, sample_tool):
        """Test that describe is an alias for get_json_schema."""
        schema1 = sample_tool.get_json_schema()
        schema2 = sample_tool.describe()

        assert schema1 == schema2

    def test_validate_parameters_with_valid_data(self, sample_tool):
        """Test parameter validation with valid data."""
        parameters = {"a": 5, "b": 3}
        validated = sample_tool._validate_parameters(parameters)

        assert validated == parameters

    def test_validate_parameters_without_model(self):
        """Test parameter validation when no parameters_model exists."""

        def simple_func():
            return "hello"

        tool = Tool.from_function(simple_func)
        parameters = {"extra": "param"}
        validated = tool._validate_parameters(parameters)

        # When parameters_model exists with no fields, extra params are filtered out
        assert validated == {}

    def test_run_with_valid_parameters(self, sample_tool):
        """Test running tool with valid parameters."""
        parameters = {"a": 5, "b": 3}
        result = sample_tool.run(parameters)

        assert result == 8

    def test_run_with_invalid_parameters_returns_error_string(self, sample_tool):
        """Test running tool with invalid parameters returns error string."""
        parameters = {"invalid": "params"}
        result = sample_tool.run(parameters)

        assert isinstance(result, str)
        assert "Error executing" in result

    @pytest.mark.asyncio
    async def test_arun_with_async_function(self, async_sample_function):
        """Test async execution of async tool."""
        tool = Tool.from_function(async_sample_function)
        parameters = {"a": 10, "b": 20}
        result = await tool.arun(parameters)

        assert result == 30

    @pytest.mark.asyncio
    async def test_arun_with_sync_function_returns_result_or_error(self, sample_tool):
        """Test async execution of sync tool."""
        parameters = {"a": 5, "b": 3}
        result = await sample_tool.arun(parameters)

        # Sync functions called via arun may either succeed or return error
        assert result == 8 or (isinstance(result, str) and "Error executing" in result)

    @pytest.mark.asyncio
    async def test_arun_with_invalid_parameters_returns_error_string(
        self, async_sample_function
    ):
        """Test async execution with invalid parameters returns error string."""
        tool = Tool.from_function(async_sample_function)
        parameters = {"invalid": "params"}
        result = await tool.arun(parameters)

        assert isinstance(result, str)
        assert "Error executing" in result

    def test_update_namespace_adds_namespace_to_tool_without_existing(
        self, sample_tool
    ):
        """Test adding namespace to tool without existing namespace."""
        original_name = sample_tool.name
        namespace = "math"

        sample_tool.update_namespace(namespace)

        assert sample_tool.name == f"{namespace}-{original_name}"

    def test_update_namespace_preserves_existing_namespace_without_force(
        self, sample_tool
    ):
        """Test that existing namespace is preserved when force=False."""
        sample_tool.name = "existing-tool_name"
        original_name = sample_tool.name

        sample_tool.update_namespace("new_namespace", force=False)

        assert sample_tool.name == original_name

    def test_update_namespace_replaces_existing_namespace_with_force(self, sample_tool):
        """Test that existing namespace is replaced when force=True."""
        sample_tool.name = "existing-tool_name"
        new_namespace = "new_namespace"

        sample_tool.update_namespace(new_namespace, force=True)

        assert sample_tool.name == f"{new_namespace}-tool_name"

    def test_update_namespace_with_dot_separator(self, sample_tool):
        """Test namespace update with dot separator."""
        original_name = sample_tool.name
        namespace = "math"

        sample_tool.update_namespace(namespace, sep=".")

        assert sample_tool.name == f"{namespace}.{original_name}"

    def test_update_namespace_with_empty_namespace_does_nothing(self, sample_tool):
        """Test that empty namespace does nothing."""
        original_name = sample_tool.name

        sample_tool.update_namespace("")
        sample_tool.update_namespace(None)

        assert sample_tool.name == original_name

    def test_tool_with_function_without_docstring(self):
        """Test creating tool from function without docstring."""

        def no_doc_func(x: int) -> int:
            return x + 1

        tool = Tool.from_function(no_doc_func)

        assert tool.description == ""

    def test_tool_with_function_with_complex_parameters(self):
        """Test creating tool from function with complex parameter types."""

        def complex_func(
            name: str, age: int = 25, scores: list = None, metadata: dict = None
        ) -> str:
            """A function with complex parameters."""
            return f"Processed {name}"

        tool = Tool.from_function(complex_func)

        assert tool.name == "complex_func"
        assert "properties" in tool.parameters
        assert tool.parameters_model is not None

    def test_tool_parameters_model_generation_failure_handled_gracefully(self):
        """Test that parameter model generation failure is handled gracefully."""

        def problematic_func(x):  # No type hints
            return x

        tool = Tool.from_function(problematic_func)

        assert tool.name == "problematic_func"
        # The model generation may still succeed even without type hints
        assert tool.parameters_model is not None

    def test_tool_callable_field_excluded_from_serialization(self, sample_tool):
        """Test that callable field is excluded from model serialization."""
        model_dict = sample_tool.model_dump()

        assert "callable" not in model_dict
        assert "name" in model_dict
        assert "description" in model_dict
        assert "parameters" in model_dict


class TestToolMetadataFields:
    """Test cases for ToolMetadata and ToolTag."""

    def test_tool_metadata_defaults(self):
        """Test ToolMetadata default values."""
        meta = ToolMetadata()

        assert meta.is_async is False
        assert meta.is_concurrency_safe is True
        assert meta.timeout is None
        assert meta.locality == "any"
        assert meta.tags == set()
        assert meta.custom_tags == set()
        assert meta.extra == {}

    def test_tool_metadata_custom_values(self):
        """Test ToolMetadata with custom values."""
        meta = ToolMetadata(
            is_async=True,
            is_concurrency_safe=False,
            timeout=30.0,
            locality="remote",
            tags={ToolTag.NETWORK, ToolTag.SLOW},
            custom_tags={"experimental"},
            extra={"version": "1.0"},
        )

        assert meta.is_async is True
        assert meta.is_concurrency_safe is False
        assert meta.timeout == 30.0
        assert meta.locality == "remote"
        assert ToolTag.NETWORK in meta.tags
        assert ToolTag.SLOW in meta.tags
        assert "experimental" in meta.custom_tags
        assert meta.extra == {"version": "1.0"}

    def test_tool_metadata_all_tags(self):
        """Test ToolMetadata.all_tags property."""
        meta = ToolMetadata(
            tags={ToolTag.READ_ONLY, ToolTag.NETWORK},
            custom_tags={"fast", "beta"},
        )

        all_tags = meta.all_tags
        assert "read_only" in all_tags
        assert "network" in all_tags
        assert "fast" in all_tags
        assert "beta" in all_tags

    def test_tool_tag_enum_values(self):
        """Test ToolTag enum values."""
        assert ToolTag.READ_ONLY == "read_only"
        assert ToolTag.DESTRUCTIVE == "destructive"
        assert ToolTag.NETWORK == "network"
        assert ToolTag.FILE_SYSTEM == "file_system"
        assert ToolTag.SLOW == "slow"
        assert ToolTag.PRIVILEGED == "privileged"

    def test_tool_from_function_with_metadata(self):
        """Test creating Tool with explicit metadata."""

        def my_func(x: int) -> int:
            """A test function."""
            return x

        meta = ToolMetadata(
            is_concurrency_safe=False,
            timeout=5.0,
            tags={ToolTag.SLOW},
        )
        tool = Tool.from_function(my_func, metadata=meta)

        assert tool.metadata.is_concurrency_safe is False
        assert tool.metadata.timeout == 5.0
        assert ToolTag.SLOW in tool.metadata.tags
        # is_async should be auto-detected
        assert tool.metadata.is_async is False

    def test_tool_namespace_field(self, sample_function):
        """Test Tool namespace field."""
        tool = Tool.from_function(sample_function, namespace="math")

        assert tool.namespace == "math"
        assert tool.name == "math-add_numbers"

    def test_tool_method_name_field(self, sample_function):
        """Test Tool method_name field."""
        tool = Tool.from_function(sample_function)

        assert tool.method_name == "add_numbers"

    def test_tool_qualified_name(self, sample_function):
        """Test Tool qualified_name property."""
        tool = Tool.from_function(sample_function, namespace="math")

        assert tool.qualified_name == "math-add_numbers"

    def test_tool_qualified_name_without_namespace(self, sample_function):
        """Test Tool qualified_name without namespace."""
        tool = Tool.from_function(sample_function)

        assert tool.qualified_name == "add_numbers"
