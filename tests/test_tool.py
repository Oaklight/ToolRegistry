"""Unit tests for the Tool class."""

import asyncio
import inspect

import dataclasses
import pytest

from toolregistry.tool import Tool, ToolMetadata, ToolTag


class TestTool:
    """Test cases for the Tool class."""

    def test_tool_creation_from_function(self, sample_function):
        """Test creating a Tool from a function."""
        tool = Tool.from_function(sample_function)

        assert tool.name == "add_numbers"
        assert "Add two numbers together" in tool.description
        assert tool.fn == sample_function
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
        assert inspect.iscoroutinefunction(tool.fn)

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
        assert tool.fn == lambda_func

    def test_tool_creation_normalizes_empty_parameters_schema(self):
        """Direct Tool construction should always produce object parameters."""
        tool = Tool(
            name="bare",
            description="Bare tool",
            parameters={},
            callable=lambda: None,
            metadata=ToolMetadata(think_augment=False),
        )

        assert tool.parameters == {"type": "object", "properties": {}}

    def test_tool_creation_normalizes_non_object_parameters_schema(self):
        """Non-object parameter schemas should be replaced with empty objects."""
        tool = Tool(
            name="bad_schema",
            description="Bad schema tool",
            parameters={"type": "string"},
            callable=lambda: None,
            metadata=ToolMetadata(think_augment=False),
        )

        assert tool.parameters == {"type": "object", "properties": {}}

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
        schema = sample_tool.get_schema("openai-responses")

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

    def test_get_json_schema_google_interactions_format(self, sample_tool):
        """Test getting JSON schema in Google Interactions format."""
        schema = sample_tool.get_schema("google-interactions")

        assert schema["type"] == "function"
        assert schema["name"] == sample_tool.name
        assert "parameters" in schema
        assert "function_declarations" not in schema

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

    def test_run_raw_deprecated(self, sample_tool):
        """Test run_raw emits deprecation warning and delegates to run."""
        parameters = {"a": 5, "b": 3}
        with pytest.warns(DeprecationWarning, match="run_raw.*deprecated"):
            result = sample_tool.run_raw(parameters)
        assert result == 8

    def test_run_raises_on_invalid_parameters(self, sample_tool):
        """Test run raises on invalid parameters (no longer swallows exceptions)."""
        parameters = {"invalid": "params"}
        with pytest.raises(Exception):
            sample_tool.run(parameters)

    @pytest.mark.asyncio
    async def test_arun_with_async_function(self, async_sample_function):
        """Test async execution of async tool."""
        tool = Tool.from_function(async_sample_function)
        parameters = {"a": 10, "b": 20}
        result = await tool.arun(parameters)

        assert result == 30

    @pytest.mark.asyncio
    async def test_arun_raw_deprecated(self, async_sample_function):
        """Test arun_raw emits deprecation warning and delegates to arun."""
        tool = Tool.from_function(async_sample_function)
        parameters = {"a": 10, "b": 20}
        with pytest.warns(DeprecationWarning, match="arun_raw.*deprecated"):
            result = await tool.arun_raw(parameters)
        assert result == 30

    @pytest.mark.asyncio
    async def test_arun_with_sync_function(self, sample_tool):
        """Test async execution of sync tool via asyncio.to_thread."""
        parameters = {"a": 5, "b": 3}
        result = await sample_tool.arun(parameters)
        assert result == 8

    @pytest.mark.asyncio
    async def test_arun_raises_on_invalid_parameters(self, async_sample_function):
        """Test arun raises on invalid parameters (no longer swallows exceptions)."""
        tool = Tool.from_function(async_sample_function)
        parameters = {"invalid": "params"}
        with pytest.raises(Exception):
            await tool.arun(parameters)

    @pytest.mark.asyncio
    async def test_arun_parallel_sync_and_async(
        self, sample_tool, async_sample_function
    ):
        """Test parallel arun with mixed sync and async tools."""
        async_tool = Tool.from_function(async_sample_function)
        results = await asyncio.gather(
            sample_tool.arun({"a": 1, "b": 1}),
            sample_tool.arun({"a": 2, "b": 2}),
            async_tool.arun({"a": 3, "b": 3}),
            async_tool.arun({"a": 4, "b": 4}),
        )
        assert results == [2, 4, 6, 8]

    def test_update_namespace_adds_namespace_to_tool_without_existing(
        self, sample_tool
    ):
        """Test adding namespace to tool without existing namespace."""
        original_name = sample_tool.name
        namespace = "math"

        updated = sample_tool.update_namespace(namespace)

        assert updated.name == f"{namespace}-{original_name}"

    def test_update_namespace_preserves_existing_namespace_without_force(
        self, sample_tool
    ):
        """Test that existing namespace is preserved when force=False."""
        tool = dataclasses.replace(sample_tool, name="existing-tool_name")
        original_name = tool.name

        updated = tool.update_namespace("new_namespace", force=False)

        assert updated.name == original_name

    def test_update_namespace_replaces_existing_namespace_with_force(self, sample_tool):
        """Test that existing namespace is replaced when force=True."""
        tool = dataclasses.replace(sample_tool, name="existing-tool_name")
        new_namespace = "new_namespace"

        updated = tool.update_namespace(new_namespace, force=True)

        assert updated.name == f"{new_namespace}-tool_name"

    def test_update_namespace_with_dot_separator(self, sample_tool):
        """Test namespace update with dot separator."""
        original_name = sample_tool.name
        namespace = "math"

        updated = sample_tool.update_namespace(namespace, sep=".")

        assert updated.name == f"{namespace}.{original_name}"

    def test_update_namespace_with_empty_namespace_does_nothing(self, sample_tool):
        """Test that empty namespace does nothing."""
        original_name = sample_tool.name

        updated = sample_tool.update_namespace("")
        assert updated.name == original_name

        updated = sample_tool.update_namespace(None)
        assert updated.name == original_name

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
        model_dict = sample_tool.to_dict()

        assert "callable" not in model_dict
        assert "name" in model_dict
        assert "description" in model_dict
        assert "parameters" in model_dict


class TestThinkAugmented:
    """Test cases for think-augmented function calling (toolcall_reason).

    Two-layer model: tool.parameters never contains toolcall_reason.
    get_schema(_think_augment=True) adds it on demand.
    """

    def test_toolcall_reason_not_in_parameters(self, sample_tool):
        """toolcall_reason is never stored in tool.parameters."""
        assert "toolcall_reason" not in sample_tool.parameters["properties"]

    def test_toolcall_reason_excluded_by_default_all_formats(self, sample_tool):
        """Standalone get_schema() excludes toolcall_reason (matches registry default)."""
        for fmt, extract in [
            ("openai-chat", lambda s: s["function"]["parameters"]["properties"]),
            ("anthropic", lambda s: s["input_schema"]["properties"]),
            ("gemini", lambda s: s["parameters"]["properties"]),
            ("google-interactions", lambda s: s["parameters"]["properties"]),
        ]:
            schema = sample_tool.get_schema(fmt)
            assert "toolcall_reason" not in extract(schema), (
                f"toolcall_reason should not appear for {fmt} by default"
            )

    def test_toolcall_reason_included_when_think_augment_true(self, sample_function):
        """get_schema(_think_augment=True) injects toolcall_reason."""
        tool = Tool.from_function(sample_function)
        for fmt, extract in [
            ("openai-chat", lambda s: s["function"]["parameters"]["properties"]),
            ("anthropic", lambda s: s["input_schema"]["properties"]),
            ("gemini", lambda s: s["parameters"]["properties"]),
            ("google-interactions", lambda s: s["parameters"]["properties"]),
        ]:
            schema = tool.get_schema(fmt, _think_augment=True)
            props = extract(schema)
            assert "toolcall_reason" in props, (
                f"toolcall_reason missing for {fmt} with think_augment=True"
            )
            assert props["toolcall_reason"]["type"].lower() == "string"

    def test_toolcall_reason_stripped_on_run(self, sample_tool):
        """toolcall_reason is stripped before execution in run()."""
        result = sample_tool.run(
            {"a": 5, "b": 3, "toolcall_reason": "I need to add these numbers"}
        )
        assert result == 8

    @pytest.mark.asyncio
    async def test_toolcall_reason_stripped_on_arun(self, async_sample_function):
        """toolcall_reason is stripped before execution in arun()."""
        tool = Tool.from_function(async_sample_function)
        result = await tool.arun(
            {"a": 10, "b": 20, "toolcall_reason": "Adding asynchronously"}
        )
        assert result == 30

    def test_native_thought_param_not_affected(self):
        """Native 'thought' parameter is not affected by toolcall_reason."""

        def func_with_thought(thought: str, value: int) -> str:
            """A function that uses thought as a real parameter."""
            return f"{thought}: {value}"

        tool = Tool.from_function(func_with_thought)
        assert "thought" in tool.parameters["properties"]
        assert "toolcall_reason" not in tool.parameters["properties"]
        result = tool.run({"thought": "hello", "value": 42, "toolcall_reason": "test"})
        assert result == "hello: 42"

    def test_manual_tool_no_toolcall_reason(self):
        """Manually created Tool does not get toolcall_reason in parameters."""
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
        assert "toolcall_reason" not in tool.parameters["properties"]

    def test_empty_schema_normalized(self):
        """Empty schema is normalized without toolcall_reason."""
        tool = Tool(
            name="empty_tool",
            description="Tool with empty schema",
            parameters={},
            callable=lambda: "ok",
        )
        assert tool.parameters == {"type": "object", "properties": {}}

    def test_think_metadata_false_excludes(self, sample_function):
        """think_augment=False excludes toolcall_reason from get_schema."""
        tool = Tool.from_function(
            sample_function, metadata=ToolMetadata(think_augment=False)
        )
        assert "toolcall_reason" not in tool.parameters["properties"]
        schema = tool.get_schema("openai-chat")
        assert "toolcall_reason" not in schema["function"]["parameters"]["properties"]

    def test_think_metadata_true_includes(self, sample_function):
        """think_augment=True includes toolcall_reason in get_schema."""
        tool = Tool.from_function(
            sample_function, metadata=ToolMetadata(think_augment=True)
        )
        schema = tool.get_schema("openai-chat")
        assert "toolcall_reason" in schema["function"]["parameters"]["properties"]

    def test_think_metadata_none_excludes_by_default(self, sample_function):
        """think_augment=None (default) excludes toolcall_reason (matches registry default)."""
        tool = Tool.from_function(sample_function)
        assert tool.metadata.think_augment is None
        schema = tool.get_schema("openai-chat")
        assert "toolcall_reason" not in schema["function"]["parameters"]["properties"]

    def test_think_override_false_strips(self, sample_function):
        """_think_augment=False override excludes toolcall_reason."""
        tool = Tool.from_function(sample_function)
        schema = tool.get_schema("openai-chat", _think_augment=False)
        assert "toolcall_reason" not in schema["function"]["parameters"]["properties"]

    def test_think_override_true_includes(self, sample_function):
        """_think_augment=True override includes toolcall_reason even if per-tool=False."""
        tool = Tool.from_function(
            sample_function, metadata=ToolMetadata(think_augment=False)
        )
        schema = tool.get_schema("openai-chat", _think_augment=True)
        assert "toolcall_reason" in schema["function"]["parameters"]["properties"]

    def test_param_named_toolcall_reason_survives(self):
        """A function with a parameter literally named toolcall_reason preserves it."""

        def func_with_reason(query: str, toolcall_reason: str = "default") -> str:
            """A function with toolcall_reason as a real parameter."""
            return f"{query}: {toolcall_reason}"

        tool = Tool.from_function(func_with_reason)
        assert "toolcall_reason" in tool.parameters["properties"]
        assert "query" in tool.parameters["properties"]


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


class TestFrozenDataclasses:
    """Test that Tool and ToolMetadata are frozen (immutable) dataclasses."""

    def test_tool_is_frozen(self):
        """Assigning to a Tool field after construction raises FrozenInstanceError."""

        def sample(a: int) -> int:
            return a

        tool = Tool.from_function(sample, name="sample")
        with pytest.raises(dataclasses.FrozenInstanceError):
            tool.name = "other"  # type: ignore[misc]

    def test_tool_metadata_is_frozen(self):
        """Assigning to a ToolMetadata field after construction raises FrozenInstanceError."""
        meta = ToolMetadata()
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.timeout = 5.0  # type: ignore[misc]

    def test_tool_metadata_replace(self):
        """dataclasses.replace() produces a new ToolMetadata with updated fields."""
        meta = ToolMetadata(timeout=1.0)
        new_meta = dataclasses.replace(meta, timeout=2.0)
        assert meta.timeout == 1.0
        assert new_meta.timeout == 2.0

    def test_tool_replace(self):
        """dataclasses.replace() produces a new Tool with updated fields."""

        def sample(a: int) -> int:
            return a

        tool = Tool.from_function(sample, name="sample")
        new_tool = dataclasses.replace(tool, description="updated")
        assert tool.description != "updated"
        assert new_tool.description == "updated"

    def test_update_namespace_returns_new_tool(self):
        """update_namespace returns a new Tool instead of mutating in place."""

        def sample(a: int) -> int:
            return a

        original = Tool.from_function(sample, name="sample")
        updated = original.update_namespace("ns")
        assert updated is not original
        assert updated.name == "ns-sample"
        assert original.name == "sample"

    def test_validate_parameters_public(self):
        """validate_parameters is accessible as a public method."""

        def sample(a: int, b: int) -> int:
            return a + b

        tool = Tool.from_function(sample, name="sample")
        result = tool.validate_parameters({"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

    def test_validate_parameters_backward_compat(self):
        """_validate_parameters still works as a backward-compat alias."""

        def sample(a: int) -> int:
            return a

        tool = Tool.from_function(sample, name="sample")
        assert tool._validate_parameters({"a": 1}) == {"a": 1}
