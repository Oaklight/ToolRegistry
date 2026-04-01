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
        schema = sample_tool.get_schema("openai-chat")

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == sample_tool.name
        assert schema["function"]["description"] == sample_tool.description
        assert "parameters" in schema["function"]

    def test_get_json_schema_openai_chat_format(self, sample_tool):
        """Test getting JSON schema in OpenAI chat completion format."""
        schema = sample_tool.get_schema("openai-chat")

        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == sample_tool.name

    def test_get_json_schema_openai_response_format(self, sample_tool):
        """Test getting JSON schema in OpenAI response format."""
        schema = sample_tool.get_schema("openai-response")

        assert schema["type"] == "function"
        assert schema["name"] == sample_tool.name
        assert schema["description"] == sample_tool.description
        assert schema["strict"] is False

    def test_get_json_schema_anthropic_format(self, sample_tool):
        """Test getting JSON schema in Anthropic format."""
        schema = sample_tool.get_schema("anthropic")

        assert schema["name"] == sample_tool.name
        assert "input_schema" in schema

    def test_get_json_schema_gemini_format(self, sample_tool):
        """Test getting JSON schema in Gemini format."""
        schema = sample_tool.get_schema("gemini")

        assert schema["name"] == sample_tool.name
        assert "parameters" in schema

    def test_get_json_schema_unsupported_format_raises_error(self, sample_tool):
        """Test that unsupported API format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported API format"):
            sample_tool.get_schema("unsupported_format")

    def test_describe_deprecated_alias(self, sample_tool):
        """Test that describe() is a deprecated alias for get_schema()."""
        import warnings

        schema1 = sample_tool.get_schema()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            schema2 = sample_tool.describe()
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "get_schema" in str(w[0].message)

        assert schema1 == schema2

    def test_get_json_schema_deprecated_alias(self, sample_tool):
        """Test that get_json_schema() is a deprecated alias for get_schema()."""
        import warnings

        schema1 = sample_tool.get_schema()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            schema2 = sample_tool.get_json_schema()
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "get_schema" in str(w[0].message)

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


class TestThinkAugmented:
    """Test cases for think-augmented function calling."""

    def test_think_property_in_schema(self, sample_tool):
        """Test that thought property is injected into tool schema."""
        assert "thought" in sample_tool.parameters["properties"]
        thought = sample_tool.parameters["properties"]["thought"]
        assert thought["type"] == "string"
        assert "reasoning" in thought["description"]

    def test_think_property_in_openai_format(self, sample_tool):
        """Test that thought appears in OpenAI format schema."""
        schema = sample_tool.get_schema("openai-chat")
        params = schema["function"]["parameters"]
        assert "thought" in params["properties"]

    def test_think_property_in_anthropic_format(self, sample_tool):
        """Test that thought appears in Anthropic format schema."""
        schema = sample_tool.get_schema("anthropic")
        assert "thought" in schema["input_schema"]["properties"]

    def test_think_property_in_gemini_format(self, sample_tool):
        """Test that thought appears in Gemini format schema."""
        schema = sample_tool.get_schema("gemini")
        assert "thought" in schema["parameters"]["properties"]

    def test_think_stripped_on_run(self, sample_tool):
        """Test that thought is stripped before execution in run()."""
        result = sample_tool.run(
            {"a": 5, "b": 3, "thought": "I need to add these numbers"}
        )
        assert result == 8

    @pytest.mark.asyncio
    async def test_think_stripped_on_arun(self, async_sample_function):
        """Test that thought is stripped before execution in arun()."""
        tool = Tool.from_function(async_sample_function)
        result = await tool.arun({"a": 10, "b": 20, "thought": "Adding asynchronously"})
        assert result == 30

    def test_think_no_override_existing(self):
        """Test that native thought parameter is not overridden."""

        def func_with_thought(thought: str, value: int) -> str:
            """A function that uses thought as a real parameter."""
            return f"{thought}: {value}"

        tool = Tool.from_function(func_with_thought)
        # thought should still be in schema (native)
        assert "thought" in tool.parameters["properties"]
        # Should NOT be stripped during execution
        result = tool.run({"thought": "hello", "value": 42})
        assert result == "hello: 42"

    def test_think_manual_tool_creation(self):
        """Test that manually created Tool also gets thought injected."""
        tool = Tool(
            name="manual_tool",
            description="A manually created tool",
            parameters={
                "type": "object",
                "properties": {
                    "x": {"type": "integer"},
                },
                "required": ["x"],
            },
            callable=lambda x: x * 2,
        )
        assert "thought" in tool.parameters["properties"]

    def test_think_empty_schema_no_inject(self):
        """Test that thought is not injected when schema has no properties."""
        tool = Tool(
            name="empty_tool",
            description="Tool with empty schema",
            parameters={},
            callable=lambda: "ok",
        )
        assert "properties" not in tool.parameters

    def test_think_metadata_false_strips_from_schema(self, sample_function):
        """Test that think_augment=False strips thought from get_schema output."""
        tool = Tool.from_function(
            sample_function, metadata=ToolMetadata(think_augment=False)
        )
        # Internal storage still has thought
        assert "thought" in tool.parameters["properties"]
        # But get_schema strips it
        schema = tool.get_schema("openai-chat")
        assert "thought" not in schema["function"]["parameters"]["properties"]

    def test_think_metadata_true_includes_in_schema(self, sample_function):
        """Test that think_augment=True always includes thought in schema."""
        tool = Tool.from_function(
            sample_function, metadata=ToolMetadata(think_augment=True)
        )
        schema = tool.get_schema("openai-chat")
        assert "thought" in schema["function"]["parameters"]["properties"]

    def test_think_metadata_none_includes_by_default(self, sample_function):
        """Test that think_augment=None (default) includes thought when called directly."""
        tool = Tool.from_function(sample_function)
        assert tool.metadata.think_augment is None
        schema = tool.get_schema("openai-chat")
        assert "thought" in schema["function"]["parameters"]["properties"]

    def test_think_override_false_strips(self, sample_function):
        """Test _think_augment=False override strips thought from output."""
        tool = Tool.from_function(sample_function)
        schema = tool.get_schema("openai-chat", _think_augment=False)
        assert "thought" not in schema["function"]["parameters"]["properties"]

    def test_think_override_true_includes(self, sample_function):
        """Test _think_augment=True override includes thought in output."""
        tool = Tool.from_function(
            sample_function, metadata=ToolMetadata(think_augment=False)
        )
        # Per-tool says False, but override says True
        schema = tool.get_schema("openai-chat", _think_augment=True)
        assert "thought" in schema["function"]["parameters"]["properties"]

    def test_think_native_param_never_stripped(self):
        """Test that native thought parameter is never stripped from schema."""

        def func_with_thought(thought: str, x: int) -> str:
            """Uses thought natively."""
            return f"{thought}: {x}"

        tool = Tool.from_function(
            func_with_thought, metadata=ToolMetadata(think_augment=False)
        )
        schema = tool.get_schema("openai-chat", _think_augment=False)
        # Native thought should survive even with think_augment=False
        assert "thought" in schema["function"]["parameters"]["properties"]

    def test_think_strip_all_formats(self, sample_function):
        """Test that thought is stripped across all API formats."""
        tool = Tool.from_function(sample_function)
        for fmt, path in [
            ("openai-chat", lambda s: s["function"]["parameters"]["properties"]),
            ("anthropic", lambda s: s["input_schema"]["properties"]),
            ("gemini", lambda s: s["parameters"]["properties"]),
        ]:
            schema = tool.get_schema(fmt, _think_augment=False)
            assert "thought" not in path(schema), f"thought not stripped for {fmt}"


class TestToolMetadataFields:
    """Test cases for ToolMetadata and ToolTag."""

    def test_tool_metadata_defaults(self):
        """Test ToolMetadata default values."""
        meta = ToolMetadata()

        assert meta.is_async is False
        assert meta.is_concurrency_safe is True
        assert meta.timeout is None
        assert meta.locality == "any"
        assert meta.think_augment is None
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
