"""Unit tests for the parameter_models module."""

import inspect
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union
from unittest.mock import Mock, patch

import pytest

from toolregistry._vendor.validate import (
    Doc,
    Ge,
    MaxLen,
    json_schema as _json_schema,
    validate as _validate,
)
from toolregistry.parameter_models import (
    InvalidSignature,
    _create_field,
    _generate_parameters_model,
    _get_typed_annotation,
)


class TestInvalidSignature:
    """Test cases for the InvalidSignature exception."""

    def test_invalid_signature_creation(self):
        """Test creating InvalidSignature exception."""
        message = "Test error message"
        exception = InvalidSignature(message)

        assert str(exception) == message
        assert isinstance(exception, Exception)


class TestParameterValidation:
    """Test parameter validation and schema generation basics."""

    def test_simple_struct_creation(self):
        """Test creating a simple parameter struct."""

        def simple(name: str, age: int = 25) -> None: ...

        model = _generate_parameters_model(simple)
        assert model is not None
        result = _validate({"name": "John", "age": 30}, model)
        assert result["name"] == "John"
        assert result["age"] == 30

    def test_validate_returns_dict(self):
        """validate() returns a plain dict, not an object with attributes."""

        def f(name: str, meta: dict[str, Any] = {}) -> None: ...  # noqa: B006

        model = _generate_parameters_model(f)
        result = _validate({"name": "Alice", "meta": {"key": "value"}}, model)
        assert isinstance(result, dict)
        assert result == {"name": "Alice", "meta": {"key": "value"}}

    def test_coercion_str_to_int(self):
        """String-encoded numbers should coerce to int."""

        def f(count: int) -> None: ...

        model = _generate_parameters_model(f)
        result = _validate({"count": "42"}, model, coerce=True)
        assert result["count"] == 42
        assert isinstance(result["count"], int)

    def test_arbitrary_type_schema_generation_requires_fallback(self):
        """Arbitrary runtime types should not block schema generation."""

        class CustomType:
            pass

        def f(custom: CustomType, name: str) -> None:
            pass

        with pytest.warns(UserWarning, match="custom.*Falling back"):
            model = _generate_parameters_model(f)

        assert model is not None
        schema = _json_schema(model)
        assert "custom" in schema["properties"]
        assert schema["properties"]["name"]["type"] == "string"


class TestGetTypedAnnotation:
    """Test cases for the _get_typed_annotation function."""

    def test_get_typed_annotation_with_type(self):
        """Test _get_typed_annotation with actual type."""
        annotation = int
        globalns = {}

        result = _get_typed_annotation(annotation, globalns)

        assert result is int

    def test_get_typed_annotation_with_string_annotation(self):
        """Test _get_typed_annotation with string annotation."""
        annotation = "int"
        globalns = {"int": int}

        result = _get_typed_annotation(annotation, globalns)

        assert result is int

    def test_get_typed_annotation_with_complex_string_annotation(self):
        """Test _get_typed_annotation with complex string annotation."""
        annotation = "List[str]"
        globalns = {"List": list, "str": str}

        result = _get_typed_annotation(annotation, globalns)

        assert result == list[str]

    def test_get_typed_annotation_with_invalid_string_raises_error(self):
        """Test _get_typed_annotation with invalid string raises InvalidSignature."""
        annotation = "NonExistentType"
        globalns = {}

        with pytest.raises(
            InvalidSignature, match="Unable to evaluate type annotation"
        ):
            _get_typed_annotation(annotation, globalns)

    def test_get_typed_annotation_with_forward_reference(self):
        """Test _get_typed_annotation with forward reference."""
        annotation = "Optional[str]"
        globalns = {"Optional": Optional, "str": str}

        result = _get_typed_annotation(annotation, globalns)

        assert result == str | None


class TestCreateField:
    """Test cases for the _create_field function."""

    def test_create_field_required_parameter_with_annotation(self):
        """Test _create_field with required parameter that has annotation."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
        )

        annotation_type, default = _create_field(param, str)

        assert annotation_type is str
        assert default is ...

    def test_create_field_required_parameter_without_annotation(self):
        """Test _create_field with required parameter without annotation."""
        param = inspect.Parameter(
            name="test_param", kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        )

        annotation_type, default = _create_field(param, Any)

        assert annotation_type is Any
        assert default is ...

    def test_create_field_optional_parameter_with_annotation(self):
        """Test _create_field respects the declared annotation (no forced | None)."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
            default="default_value",
        )

        annotation_type, default = _create_field(param, str)

        assert annotation_type is str
        assert default == "default_value"

    def test_create_field_optional_parameter_without_annotation(self):
        """Test _create_field with optional parameter without annotation."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=42,
        )

        annotation_type, default = _create_field(param, Any)

        assert annotation_type == Any | None
        assert default == 42

    def test_create_field_with_none_default(self):
        """Test _create_field with None default respects declared annotation."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
            default=None,
        )

        annotation_type, default = _create_field(param, str)

        assert annotation_type is str
        assert default is None


class TestGenerateParametersModel:
    """Test cases for the _generate_parameters_model function."""

    def test_generate_parameters_model_simple_function(self):
        """Test generating parameters model for simple function."""

        def simple_func(name: str, age: int) -> str:
            return f"{name} is {age} years old"

        model_class = _generate_parameters_model(simple_func)

        assert model_class is not None
        assert model_class.__name__ == "simple_funcParameters"

        result = _validate({"name": "John", "age": 25}, model_class)
        assert result["name"] == "John"
        assert result["age"] == 25

    def test_generate_parameters_model_function_with_defaults(self):
        """Test generating parameters model for function with default values."""

        def func_with_defaults(name: str, age: int = 30, city: str = "Unknown") -> str:
            return f"{name}, {age}, {city}"

        model_class = _generate_parameters_model(func_with_defaults)

        assert model_class is not None

        result1 = _validate({"name": "Alice", "age": 25, "city": "NYC"}, model_class)
        assert result1["name"] == "Alice"
        assert result1["age"] == 25

        result2 = _validate({"name": "Bob"}, model_class)
        assert result2["name"] == "Bob"

    def test_generate_parameters_model_function_without_annotations(self):
        """Test generating parameters model for function without type annotations."""

        def func_no_annotations(x, y=10):
            return x + y

        model_class = _generate_parameters_model(func_no_annotations)

        assert model_class is not None

        result = _validate({"x": "hello", "y": "world"}, model_class)
        assert result["x"] == "hello"

    def test_generate_parameters_model_function_with_complex_types(self):
        """Test generating parameters model for function with complex types."""

        def complex_func(
            items: list[str],
            metadata: dict[str, Any],
            optional_flag: bool | None = None,
        ) -> dict[str, Any]:
            return {"items": items, "metadata": metadata, "flag": optional_flag}

        model_class = _generate_parameters_model(complex_func)

        assert model_class is not None

        result = _validate(
            {
                "items": ["a", "b", "c"],
                "metadata": {"key": "value"},
                "optional_flag": True,
            },
            model_class,
        )
        assert result["items"] == ["a", "b", "c"]
        assert result["metadata"] == {"key": "value"}
        assert result["optional_flag"] is True

    def test_generate_parameters_model_method_skips_self(self):
        """Test that 'self' parameter is skipped for methods."""

        class TestClass:
            def method(self, name: str, value: int) -> str:
                return f"{name}: {value}"

        model_class = _generate_parameters_model(TestClass.method)

        assert model_class is not None

        result = _validate({"name": "test", "value": 42}, model_class)
        assert result["name"] == "test"
        assert result["value"] == 42

        assert (
            "self" not in model_class.__required_keys__ | model_class.__optional_keys__
        )

    def test_generate_parameters_model_function_with_union_types(self):
        """Test generating parameters model for function with Union types."""

        def union_func(value: Union[str, int], flag: bool = True) -> str:
            return str(value)

        model_class = _generate_parameters_model(union_func)

        assert model_class is not None

        result1 = _validate({"value": "hello", "flag": False}, model_class)
        assert result1["value"] == "hello"
        assert result1["flag"] is False

        result2 = _validate({"value": 42}, model_class)
        assert result2["value"] == 42

    def test_generate_parameters_model_no_parameters(self):
        """Test generating parameters model for function with no parameters."""

        def no_params_func() -> str:
            return "hello"

        model_class = _generate_parameters_model(no_params_func)

        assert model_class is not None

        result = _validate({}, model_class)
        assert result == {}

    def test_generate_parameters_model_with_string_annotations(self):
        """Test generating parameters model with string annotations."""

        def func_with_string_annotations(name: "str", count: "int" = 1) -> "str":
            return name * count

        model_class = _generate_parameters_model(func_with_string_annotations)

        assert model_class is not None

        result = _validate({"name": "hello", "count": 3}, model_class)
        assert result["name"] == "hello"
        assert result["count"] == 3

    def test_generate_parameters_model_unresolved_annotation_falls_back(self):
        """Unresolved annotations should fall back per parameter instead of failing."""

        def problematic_func(x) -> str:
            return str(x)

        problematic_func.__annotations__ = {"x": "NonExistentType", "return": str}

        with pytest.warns(UserWarning, match="Falling back"):
            model_class = _generate_parameters_model(problematic_func)

        assert model_class is not None
        schema = _json_schema(model_class)
        assert schema["type"] == "object"
        assert "x" in schema["properties"]

    def test_generate_parameters_model_mixed_unresolved_annotation_keeps_valid_fields(
        self,
    ):
        """A bad annotation should not discard other valid parameter schemas."""

        def mixed_func(name: str, value) -> str:
            return f"{name}:{value}"

        mixed_func.__annotations__ = {
            "name": str,
            "value": "MissingRuntimeType",
            "return": str,
        }

        with pytest.warns(UserWarning, match="value.*Falling back"):
            model_class = _generate_parameters_model(mixed_func)

        assert model_class is not None
        schema = _json_schema(model_class)
        assert schema["properties"]["name"]["type"] == "string"
        assert "value" in schema["properties"]

    def test_generate_parameters_model_with_invalid_signature(self):
        """Test generating parameters model with function that has invalid signature."""
        mock_func = Mock()
        mock_func.__name__ = "mock_func"

        with patch("inspect.signature", side_effect=ValueError("Invalid signature")):
            model_class = _generate_parameters_model(mock_func)

        assert model_class is None

    def test_validate_integration(self):
        """Test integration of validate with generated model."""

        def test_func(name: str, age: int = 25, active: bool = True) -> str:
            return f"{name}-{age}-{active}"

        model_class = _generate_parameters_model(test_func)
        result = _validate({"name": "test", "age": 30}, model_class)

        assert result["name"] == "test"
        assert result["age"] == 30

    def test_generate_parameters_model_preserves_function_name(self):
        """Test that generated model class name includes function name."""

        def my_custom_function(x: int) -> int:
            return x * 2

        model_class = _generate_parameters_model(my_custom_function)

        assert model_class.__name__ == "my_custom_functionParameters"

    def test_generate_parameters_model_with_lambda(self):
        """Test generating parameters model for lambda function."""
        lambda_func = lambda x, y=10: x + y  # noqa: E731
        lambda_func.__name__ = "lambda_func"

        model_class = _generate_parameters_model(lambda_func)

        assert model_class is not None

        result = _validate({"x": 5, "y": 15}, model_class)
        assert result["x"] == 5
        assert result["y"] == 15


class TestComplexTypeSchemaGeneration:
    """Test edge cases with complex type annotations and JSON Schema output."""

    @staticmethod
    def _schema_for(func):
        """Generate JSON Schema from function parameters."""
        model = _generate_parameters_model(func)
        assert model is not None, f"Model generation failed for {func.__name__}"
        return _json_schema(model)

    # --- Union / anyOf ---

    def test_union_produces_anyof(self):
        """Union[str, int] should produce oneOf/anyOf in schema."""

        def f(value: Union[str, int]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["value"]
        assert "oneOf" in prop or "anyOf" in prop
        key = "oneOf" if "oneOf" in prop else "anyOf"
        types = {branch.get("type") for branch in prop[key]}
        assert types == {"string", "integer"}

    def test_pipe_union_produces_anyof(self):
        """str | int (PEP 604) should produce oneOf/anyOf in schema."""

        def f(value: str | int) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["value"]
        assert "oneOf" in prop or "anyOf" in prop

    # --- Nested generic types ---

    def test_list_str(self):
        """list[str] should produce array with string items."""

        def f(items: list[str]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["items"]
        assert prop["type"] == "array"
        assert prop["items"]["type"] == "string"

    def test_dict_str_int(self):
        """dict[str, int] should produce object with additionalProperties."""

        def f(mapping: dict[str, int]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["mapping"]
        assert prop["type"] == "object"
        assert prop["additionalProperties"]["type"] == "integer"

    # --- Nested dataclass ---

    def test_nested_dataclass(self):
        """A dataclass parameter should produce inline schema."""
        from dataclasses import dataclass

        @dataclass
        class Address:
            city: str
            zip_code: str

        def f(addr: Address) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["addr"]
        assert "properties" in prop
        assert "city" in prop["properties"]
        assert "zip_code" in prop["properties"]

    # --- Literal ---

    def test_literal_produces_enum(self):
        """Literal['a', 'b', 'c'] should produce an enum constraint."""

        def f(mode: Literal["a", "b", "c"]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["mode"]
        assert prop["enum"] == ["a", "b", "c"]

    def test_literal_int(self):
        """Literal[1, 2, 3] should produce an enum with integers."""

        def f(level: Literal[1, 2, 3]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["level"]
        assert prop["enum"] == [1, 2, 3]

    # --- Annotated with constraints ---

    def test_annotated_with_ge_constraint(self):
        """Annotated[int, Ge(0)] should produce minimum constraint."""

        def f(count: Annotated[int, Ge(0)]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["count"]
        assert prop["type"] == "integer"
        assert prop.get("minimum") == 0

    def test_annotated_with_max_length(self):
        """Annotated[str, MaxLen(10)] should produce maxLength."""

        def f(name: Annotated[str, MaxLen(10)]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["name"]
        assert prop["type"] == "string"
        assert prop.get("maxLength") == 10

    def test_annotated_with_description(self):
        """Annotated[int, Doc('...')] should carry description."""

        def f(x: Annotated[int, Doc("The x value")]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["x"]
        assert prop.get("description") == "The x value"

    # --- Optional[list[str]] ---

    def test_optional_list(self):
        """Optional[list[str]] should produce nullable array."""

        def f(tags: list[str] | None = None) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["tags"]
        prop_str = str(prop)
        assert "array" in prop_str or "items" in prop_str

    # --- Enum subclass ---

    def test_enum_parameter(self):
        """Enum subclass parameters should produce enum constraint."""

        class Color(str, Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

        def f(color: Color) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["color"]
        assert set(prop.get("enum", [])) == {"red", "green", "blue"}

    # --- Default values with complex types ---

    def test_default_empty_list(self):
        """Default value of [] should work for list[str] parameter."""

        def f(items: list[str] = []) -> None: ...  # noqa: B006

        model = _generate_parameters_model(f)
        assert model is not None

    def test_default_dict(self):
        """Default value of {} should work for dict parameter."""

        def f(meta: dict[str, int] = {}) -> None: ...  # noqa: B006

        model = _generate_parameters_model(f)
        assert model is not None

    # --- *args / **kwargs warnings ---

    def test_args_emits_warning(self):
        """*args parameter should emit UserWarning and be excluded."""

        def f(x: int, *args) -> None: ...

        with pytest.warns(UserWarning, match=r"\*args"):
            model = _generate_parameters_model(f)

        assert model is not None
        schema = _json_schema(model)
        assert "args" not in schema["properties"]
        assert "x" in schema["properties"]

    def test_kwargs_enables_additional_properties(self):
        """**kwargs parameter should set additionalProperties: true."""

        def f(x: int, **kwargs) -> None: ...

        model = _generate_parameters_model(f)

        assert model is not None
        schema = _json_schema(model)
        assert "kwargs" not in schema.get("properties", {})
        assert "x" in schema["properties"]
        assert getattr(model, "_has_var_keyword", False) is True

    def test_kwargs_only_function(self):
        """Function with only **kwargs should produce additionalProperties schema."""

        def f(**kwargs) -> None: ...

        model = _generate_parameters_model(f)

        assert model is not None
        assert getattr(model, "_has_var_keyword", False) is True

    def test_args_and_kwargs_combo(self):
        """*args warns while **kwargs enables additionalProperties."""

        def f(x: int, *args, **kwargs) -> None: ...

        with pytest.warns(UserWarning, match=r"\*args"):
            model = _generate_parameters_model(f)

        assert model is not None
        schema = _json_schema(model)
        assert "x" in schema["properties"]
        assert "args" not in schema.get("properties", {})
        assert getattr(model, "_has_var_keyword", False) is True

    def test_normal_function_no_additional_properties(self):
        """Normal functions should NOT have additionalProperties in schema."""

        def f(name: str, age: int = 0) -> None: ...

        schema = self._schema_for(f)
        assert "additionalProperties" not in schema

    # --- Required fields tracking ---

    def test_required_fields_in_schema(self):
        """Required parameters should appear in schema 'required' list."""

        def f(name: str, age: int, city: str = "NYC") -> None: ...

        schema = self._schema_for(f)
        assert "name" in schema.get("required", [])
        assert "age" in schema.get("required", [])
        assert "city" not in schema.get("required", [])

    # --- Mixed complex scenario ---

    def test_mixed_complex_types(self):
        """Function with many complex types should produce valid schema."""

        class Priority(str, Enum):
            LOW = "low"
            HIGH = "high"

        def process(
            name: str,
            tags: list[str],
            priority: Priority = Priority.LOW,
            count: Annotated[int, Ge(0)] = 0,
            mode: Literal["fast", "slow"] = "fast",
            extra: dict[str, Any] | None = None,
        ) -> None: ...

        schema = self._schema_for(process)
        props = schema["properties"]

        assert "name" in props
        assert "tags" in props
        assert "priority" in props
        assert "count" in props
        assert "mode" in props
        assert "extra" in props

        assert "name" in schema.get("required", [])
        assert "tags" in schema.get("required", [])
