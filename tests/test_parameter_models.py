"""Unit tests for the parameter_models module."""

import inspect
from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union
from unittest.mock import Mock, patch

import pytest
from pydantic import Field
from pydantic.fields import FieldInfo

from toolregistry.parameter_models import (
    ArgModelBase,
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


class TestArgModelBase:
    """Test cases for the ArgModelBase class."""

    def test_arg_model_base_creation(self):
        """Test creating an ArgModelBase instance."""

        class TestModel(ArgModelBase):
            name: str
            age: int = 25

        model = TestModel(name="John", age=30)

        assert model.name == "John"
        assert model.age == 30

    def test_model_dump_one_level(self):
        """Test model_dump_one_level method."""

        class TestModel(ArgModelBase):
            name: str
            age: int
            metadata: dict[str, Any] = {}

        model = TestModel(name="Alice", age=25, metadata={"key": "value"})

        dumped = model.model_dump_one_level()

        assert dumped == {"name": "Alice", "age": 25, "metadata": {"key": "value"}}

    def test_model_dump_one_level_with_nested_models(self):
        """Test model_dump_one_level with nested models."""

        class NestedModel(ArgModelBase):
            value: str

        class TestModel(ArgModelBase):
            name: str
            nested: NestedModel

        nested = NestedModel(value="nested_value")
        model = TestModel(name="test", nested=nested)

        dumped = model.model_dump_one_level()

        assert dumped["name"] == "test"
        assert isinstance(dumped["nested"], NestedModel)
        assert dumped["nested"].value == "nested_value"

    def test_arbitrary_types_allowed(self):
        """Test that arbitrary types are allowed in ArgModelBase."""

        class CustomType:
            def __init__(self, value):
                self.value = value

        class TestModel(ArgModelBase):
            custom: CustomType

        custom_obj = CustomType("test")
        model = TestModel(custom=custom_obj)

        assert model.custom == custom_obj
        assert model.custom.value == "test"


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

        annotation_type, field_info = _create_field(param, str)

        assert annotation_type is str
        assert isinstance(field_info, FieldInfo)
        from pydantic_core import PydanticUndefined

        assert field_info.default is PydanticUndefined

    def test_create_field_required_parameter_without_annotation(self):
        """Test _create_field with required parameter without annotation."""
        param = inspect.Parameter(
            name="test_param", kind=inspect.Parameter.POSITIONAL_OR_KEYWORD
        )

        annotation_type, field_info = _create_field(param, Any)

        assert annotation_type is Any
        assert isinstance(field_info, FieldInfo)
        assert field_info.title == "test_param"

    def test_create_field_optional_parameter_with_annotation(self):
        """Test _create_field with optional parameter that has annotation."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
            default="default_value",
        )

        annotation_type, field_info = _create_field(param, str)

        assert annotation_type == str | None
        assert isinstance(field_info, FieldInfo)
        assert field_info.default == "default_value"

    def test_create_field_optional_parameter_without_annotation(self):
        """Test _create_field with optional parameter without annotation."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=42,
        )

        annotation_type, field_info = _create_field(param, Any)

        assert annotation_type == Any | None
        assert isinstance(field_info, FieldInfo)
        assert field_info.default == 42
        assert field_info.title == "test_param"

    def test_create_field_with_none_default(self):
        """Test _create_field with None as default value."""
        param = inspect.Parameter(
            name="test_param",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=str,
            default=None,
        )

        annotation_type, field_info = _create_field(param, str)

        assert annotation_type == str | None
        assert field_info.default is None


class TestGenerateParametersModel:
    """Test cases for the _generate_parameters_model function."""

    def test_generate_parameters_model_simple_function(self):
        """Test generating parameters model for simple function."""

        def simple_func(name: str, age: int) -> str:
            return f"{name} is {age} years old"

        model_class = _generate_parameters_model(simple_func)

        assert model_class is not None
        assert issubclass(model_class, ArgModelBase)
        assert model_class.__name__ == "simple_funcParameters"

        # Test model instantiation
        model = model_class(name="John", age=25)
        assert model.name == "John"
        assert model.age == 25

    def test_generate_parameters_model_function_with_defaults(self):
        """Test generating parameters model for function with default values."""

        def func_with_defaults(name: str, age: int = 30, city: str = "Unknown") -> str:
            return f"{name}, {age}, {city}"

        model_class = _generate_parameters_model(func_with_defaults)

        assert model_class is not None

        # Test with all parameters
        model1 = model_class(name="Alice", age=25, city="NYC")
        assert model1.name == "Alice"
        assert model1.age == 25
        assert model1.city == "NYC"

        # Test with only required parameter
        model2 = model_class(name="Bob")
        assert model2.name == "Bob"
        assert model2.age == 30  # Default value
        assert model2.city == "Unknown"  # Default value

    def test_generate_parameters_model_function_without_annotations(self):
        """Test generating parameters model for function without type annotations."""

        def func_no_annotations(x, y=10):
            return x + y

        model_class = _generate_parameters_model(func_no_annotations)

        assert model_class is not None

        # Should work with any types
        model = model_class(x="hello", y="world")
        assert model.x == "hello"
        assert model.y == "world"

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

        model = model_class(
            items=["a", "b", "c"], metadata={"key": "value"}, optional_flag=True
        )
        assert model.items == ["a", "b", "c"]
        assert model.metadata == {"key": "value"}
        assert model.optional_flag is True

    def test_generate_parameters_model_method_skips_self(self):
        """Test that 'self' parameter is skipped for methods."""

        class TestClass:
            def method(self, name: str, value: int) -> str:
                return f"{name}: {value}"

        model_class = _generate_parameters_model(TestClass.method)

        assert model_class is not None

        # Should not include 'self' parameter
        model = model_class(name="test", value=42)
        assert model.name == "test"
        assert model.value == 42

        # Verify 'self' is not in the model fields
        assert "self" not in model.__pydantic_fields__

    def test_generate_parameters_model_function_with_union_types(self):
        """Test generating parameters model for function with Union types."""

        def union_func(value: Union[str, int], flag: bool = True) -> str:
            return str(value)

        model_class = _generate_parameters_model(union_func)

        assert model_class is not None

        # Test with string
        model1 = model_class(value="hello", flag=False)
        assert model1.value == "hello"
        assert model1.flag is False

        # Test with int
        model2 = model_class(value=42)
        assert model2.value == 42
        assert model2.flag is True

    def test_generate_parameters_model_no_parameters(self):
        """Test generating parameters model for function with no parameters."""

        def no_params_func() -> str:
            return "hello"

        model_class = _generate_parameters_model(no_params_func)

        assert model_class is not None

        # Should be able to create model with no arguments
        model = model_class()
        assert isinstance(model, ArgModelBase)

    def test_generate_parameters_model_with_string_annotations(self):
        """Test generating parameters model with string annotations."""

        def func_with_string_annotations(name: "str", count: "int" = 1) -> "str":
            return name * count

        model_class = _generate_parameters_model(func_with_string_annotations)

        assert model_class is not None

        model = model_class(name="hello", count=3)
        assert model.name == "hello"
        assert model.count == 3

    def test_generate_parameters_model_exception_handling(self):
        """Test that exceptions during model generation are handled gracefully."""

        def problematic_func(x) -> str:
            return str(x)

        # Manually set a problematic annotation that will cause issues
        problematic_func.__annotations__ = {"x": "NonExistentType", "return": str}

        # Should return None instead of raising exception
        model_class = _generate_parameters_model(problematic_func)

        assert model_class is None

    def test_generate_parameters_model_with_invalid_signature(self):
        """Test generating parameters model with function that has invalid signature."""
        mock_func = Mock()
        mock_func.__name__ = "mock_func"

        with patch("inspect.signature", side_effect=ValueError("Invalid signature")):
            model_class = _generate_parameters_model(mock_func)

        assert model_class is None

    def test_model_dump_one_level_integration(self):
        """Test integration of model_dump_one_level with generated model."""

        def test_func(name: str, age: int = 25, active: bool = True) -> str:
            return f"{name}-{age}-{active}"

        model_class = _generate_parameters_model(test_func)
        model = model_class(name="test", age=30)

        dumped = model.model_dump_one_level()

        assert dumped == {
            "name": "test",
            "age": 30,
            "active": True,  # Default value
        }

    def test_generate_parameters_model_preserves_function_name(self):
        """Test that generated model class name includes function name."""

        def my_custom_function(x: int) -> int:
            return x * 2

        model_class = _generate_parameters_model(my_custom_function)

        assert model_class.__name__ == "my_custom_functionParameters"

    def test_generate_parameters_model_with_lambda(self):
        """Test generating parameters model for lambda function."""
        lambda_func = lambda x, y=10: x + y  # noqa: E731
        lambda_func.__name__ = "lambda_func"  # Give it a name for testing

        model_class = _generate_parameters_model(lambda_func)

        assert model_class is not None

        model = model_class(x=5, y=15)
        assert model.x == 5
        assert model.y == 15


class TestComplexTypeSchemaGeneration:
    """Test edge cases with complex type annotations and JSON Schema output."""

    @staticmethod
    def _schema_for(func):
        """Generate JSON Schema from function parameters."""
        model = _generate_parameters_model(func)
        assert model is not None, f"Model generation failed for {func.__name__}"
        return model.model_json_schema()

    # --- Union / anyOf ---

    def test_union_produces_anyof(self):
        """Union[str, int] should produce anyOf in schema."""

        def f(value: Union[str, int]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["value"]
        assert "anyOf" in prop
        types = {branch.get("type") for branch in prop["anyOf"]}
        assert types == {"string", "integer"}

    def test_pipe_union_produces_anyof(self):
        """str | int (PEP 604) should produce anyOf in schema."""

        def f(value: str | int) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["value"]
        assert "anyOf" in prop

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

    # --- Nested Pydantic BaseModel ---

    def test_nested_pydantic_model(self):
        """A Pydantic BaseModel parameter should produce a $ref or inline schema."""
        from pydantic import BaseModel

        class Address(BaseModel):
            city: str
            zip_code: str

        def f(addr: Address) -> None: ...

        schema = self._schema_for(f)
        # The property should reference the Address schema
        prop = schema["properties"]["addr"]
        assert "$ref" in prop or "properties" in prop

        # Address schema should be in $defs or inline
        if "$ref" in prop:
            assert "$defs" in schema
            assert "Address" in schema["$defs"]
            addr_schema = schema["$defs"]["Address"]
            assert "city" in addr_schema["properties"]
            assert "zip_code" in addr_schema["properties"]

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

    # --- Annotated with Field constraints ---

    def test_annotated_with_ge_constraint(self):
        """Annotated[int, Field(ge=0)] should produce minimum constraint."""

        def f(count: Annotated[int, Field(ge=0)]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["count"]
        assert prop["type"] == "integer"
        assert prop.get("minimum") == 0

    def test_annotated_with_max_length(self):
        """Annotated[str, Field(max_length=10)] should produce maxLength."""

        def f(name: Annotated[str, Field(max_length=10)]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["name"]
        assert prop["type"] == "string"
        assert prop.get("maxLength") == 10

    def test_annotated_with_description(self):
        """Annotated[int, Field(description='...')] should carry description."""

        def f(x: Annotated[int, Field(description="The x value")]) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["x"]
        assert prop.get("description") == "The x value"

    # --- Optional[list[str]] ---

    def test_optional_list(self):
        """Optional[list[str]] should produce nullable array."""

        def f(tags: list[str] | None = None) -> None: ...

        schema = self._schema_for(f)
        prop = schema["properties"]["tags"]
        # Pydantic may express this as anyOf with array + null, or type array with default
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
        # Could be inline enum or $ref to Color
        prop = schema["properties"]["color"]
        if "$ref" in prop:
            color_schema = schema["$defs"]["Color"]
            assert set(color_schema["enum"]) == {"red", "green", "blue"}
        else:
            assert set(prop["enum"]) == {"red", "green", "blue"}

    # --- Default values with complex types ---

    def test_default_empty_list(self):
        """Default value of [] should work for list[str] parameter."""

        def f(items: list[str] = []) -> None: ...  # noqa: B006

        model = _generate_parameters_model(f)
        assert model is not None
        instance = model()
        assert instance.items == []

    def test_default_dict(self):
        """Default value of {} should work for dict parameter."""

        def f(meta: dict[str, int] = {}) -> None: ...  # noqa: B006

        model = _generate_parameters_model(f)
        assert model is not None
        instance = model()
        assert instance.meta == {}

    # --- *args / **kwargs warnings ---

    def test_args_emits_warning(self):
        """*args parameter should emit UserWarning and be excluded."""

        def f(x: int, *args) -> None: ...

        with pytest.warns(UserWarning, match=r"\*args"):
            model = _generate_parameters_model(f)

        assert model is not None
        assert "args" not in model.model_json_schema()["properties"]
        assert "x" in model.model_json_schema()["properties"]

    def test_kwargs_emits_warning(self):
        """**kwargs parameter should emit UserWarning and be excluded."""

        def f(x: int, **kwargs) -> None: ...

        with pytest.warns(UserWarning, match=r"\*\*kwargs"):
            model = _generate_parameters_model(f)

        assert model is not None
        assert "kwargs" not in model.model_json_schema()["properties"]
        assert "x" in model.model_json_schema()["properties"]

    # --- Required fields tracking ---

    def test_required_fields_in_schema(self):
        """Required parameters should appear in schema 'required' list."""

        def f(name: str, age: int, city: str = "NYC") -> None: ...

        schema = self._schema_for(f)
        assert "name" in schema.get("required", [])
        assert "age" in schema.get("required", [])
        # city has default, should not be required
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
            count: Annotated[int, Field(ge=0)] = 0,
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

        # name should be required
        assert "name" in schema.get("required", [])
        assert "tags" in schema.get("required", [])
