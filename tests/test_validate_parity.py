"""Exhaustive parity tests: zerodep validate vs Pydantic.

Compares behavior across every dimension the migration depends on:
type validation, coercion, schema generation, defaults, constraints,
error handling, and edge cases.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Any, Literal, Union

import pytest
from pydantic import BaseModel, ConfigDict, Field, create_model

from toolregistry._vendor.validate import (
    Ge,
    Le,
    ValidationError,
    create_struct,
    json_schema as zd_json_schema,
    validate as zd_validate,
)
from toolregistry.parameter_models import (
    _generate_parameters_model,
    _simplify_nullable_schemas,
    _resolve_enum,
    _translate_annotated_metadata,
)


# ── Helpers ────────────────────────────────────────────────────────


class _PydanticBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


def _pydantic_schema(func):
    """Generate schema via Pydantic create_model (old path)."""
    import inspect
    from typing import get_type_hints

    sig = inspect.signature(func)
    globalns = getattr(func, "__globals__", {})
    try:
        hints = get_type_hints(func, globalns, include_extras=True)
    except Exception:
        hints = {}

    fields = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        ann = hints.get(name, param.annotation)
        if ann is inspect.Parameter.empty:
            ann = Any
        if param.default is inspect.Parameter.empty:
            fields[name] = (ann, Field())
        else:
            fields[name] = (ann, Field(default=param.default))

    model = create_model(f"{func.__name__}Params", __base__=_PydanticBase, **fields)
    return model.model_json_schema()


def _zerodep_schema(func):
    """Generate schema via zerodep (new path)."""
    model = _generate_parameters_model(func)
    assert model is not None
    schema = zd_json_schema(model)
    if getattr(model, "_has_var_keyword", False):
        schema["additionalProperties"] = True
    return _simplify_nullable_schemas(schema)


# ═══════════════════════════════════════════════════════════════════
# 1. BASIC TYPE VALIDATION
# ═══════════════════════════════════════════════════════════════════


class TestBasicTypes:
    """Both engines accept correct types and reject wrong ones."""

    @pytest.mark.parametrize(
        "tp,good,bad",
        [
            (str, "hello", 123),
            (int, 42, "not_a_number"),
            (float, 3.14, "not_a_float"),
            (bool, True, "not_a_bool"),
        ],
    )
    def test_accept_correct_reject_wrong(self, tp, good, bad):
        T = create_struct("T", {"v": (tp, ...)})
        assert zd_validate({"v": good}, T)["v"] == good
        with pytest.raises(ValidationError):
            zd_validate({"v": bad}, T)

    def test_none_type(self):
        T = create_struct("T", {"v": (type(None), ...)})
        assert zd_validate({"v": None}, T)["v"] is None


# ═══════════════════════════════════════════════════════════════════
# 2. COERCION (the critical LLM path)
# ═══════════════════════════════════════════════════════════════════


class TestCoercion:
    """LLMs send string-encoded numbers. Both engines must coerce."""

    def test_str_to_int(self):
        """Pydantic: '42' → 42.  zerodep: same with coerce=True."""
        T = create_struct("T", {"n": (int, ...)})
        r = zd_validate({"n": "42"}, T, coerce=True)
        assert r["n"] == 42
        assert isinstance(r["n"], int)

    def test_str_to_float(self):
        T = create_struct("T", {"n": (float, ...)})
        r = zd_validate({"n": "3.14"}, T, coerce=True)
        assert r["n"] == 3.14
        assert isinstance(r["n"], float)

    def test_int_accepted_for_float(self):
        """int is accepted for float (numeric tower) without conversion."""
        T = create_struct("T", {"n": (float, ...)})
        r = zd_validate({"n": 5}, T, coerce=True)
        assert r["n"] == 5.0  # numerically equal
        # int stays as int (accepted via numeric tower, not coerced)
        assert isinstance(r["n"], (int, float))

    def test_no_coerce_str_to_int_fails(self):
        """Without coerce=True, string→int should fail."""
        T = create_struct("T", {"n": (int, ...)})
        with pytest.raises(ValidationError):
            zd_validate({"n": "42"}, T, coerce=False)

    def test_str_to_bool_not_coerced(self):
        """zerodep does NOT coerce str→bool (Pydantic does)."""
        T = create_struct("T", {"v": (bool, ...)})
        with pytest.raises(ValidationError):
            zd_validate({"v": "true"}, T, coerce=True)

    def test_bool_not_treated_as_int(self):
        """True should not pass as int."""
        T = create_struct("T", {"v": (int, ...)})
        with pytest.raises(ValidationError):
            zd_validate({"v": True}, T)

    def test_nested_struct_coercion(self):
        """Coercion must propagate through nested structs."""
        Inner = create_struct("Inner", {"count": (int, ...)})
        Outer = create_struct("Outer", {"inner": (Inner, ...), "name": (str, ...)})
        r = zd_validate({"inner": {"count": "7"}, "name": "test"}, Outer, coerce=True)
        assert r["inner"]["count"] == 7
        assert isinstance(r["inner"]["count"], int)

    def test_coercion_in_list(self):
        """Coercion inside list items."""
        T = create_struct("T", {"items": (list[int], ...)})
        r = zd_validate({"items": ["1", "2", "3"]}, T, coerce=True)
        assert r["items"] == [1, 2, 3]


# ═══════════════════════════════════════════════════════════════════
# 3. OPTIONAL / NULLABLE
# ═══════════════════════════════════════════════════════════════════


class TestOptionalNullable:
    """Optional[T] and T | None handling."""

    def test_optional_accepts_none(self):
        T = create_struct("T", {"v": (str | None, ...)})
        assert zd_validate({"v": None}, T)["v"] is None

    def test_optional_accepts_value(self):
        T = create_struct("T", {"v": (int | None, ...)})
        assert zd_validate({"v": 42}, T)["v"] == 42

    def test_pipe_union_none(self):
        T = create_struct("T", {"v": (str | None, ...)})
        assert zd_validate({"v": None}, T)["v"] is None
        assert zd_validate({"v": "hello"}, T)["v"] == "hello"

    def test_missing_optional_field(self):
        """Optional field with default should not be required."""
        T = create_struct("T", {"v": (str | None, None)})
        r = zd_validate({}, T)
        assert r == {}  # zerodep doesn't fill defaults


# ═══════════════════════════════════════════════════════════════════
# 4. UNION TYPES
# ═══════════════════════════════════════════════════════════════════


class TestUnionTypes:
    def test_union_str_int_accepts_both(self):
        T = create_struct("T", {"v": (Union[str, int], ...)})
        assert zd_validate({"v": "hello"}, T)["v"] == "hello"
        assert zd_validate({"v": 42}, T)["v"] == 42

    def test_union_rejects_wrong_type(self):
        T = create_struct("T", {"v": (Union[str, int], ...)})
        with pytest.raises(ValidationError):
            zd_validate({"v": [1, 2]}, T)


# ═══════════════════════════════════════════════════════════════════
# 5. COLLECTION TYPES
# ═══════════════════════════════════════════════════════════════════


class TestCollectionTypes:
    def test_list_str(self):
        T = create_struct("T", {"v": (list[str], ...)})
        r = zd_validate({"v": ["a", "b"]}, T)
        assert r["v"] == ["a", "b"]

    def test_list_rejects_wrong_item(self):
        T = create_struct("T", {"v": (list[int], ...)})
        with pytest.raises(ValidationError):
            zd_validate({"v": ["not_int"]}, T)

    def test_dict_str_int(self):
        T = create_struct("T", {"v": (dict[str, int], ...)})
        r = zd_validate({"v": {"a": 1, "b": 2}}, T)
        assert r["v"] == {"a": 1, "b": 2}

    def test_nested_list_of_dicts(self):
        T = create_struct("T", {"v": (list[dict[str, int]], ...)})
        r = zd_validate({"v": [{"a": 1}, {"b": 2}]}, T)
        assert r["v"] == [{"a": 1}, {"b": 2}]

    def test_set_type(self):
        T = create_struct("T", {"v": (set[int], ...)})
        r = zd_validate({"v": {1, 2, 3}}, T)
        assert r["v"] == {1, 2, 3}

    def test_tuple_variable_length(self):
        T = create_struct("T", {"v": (tuple[int, ...], ...)})
        r = zd_validate({"v": (1, 2, 3)}, T)
        assert set(r["v"]) == {1, 2, 3}


# ═══════════════════════════════════════════════════════════════════
# 6. LITERAL TYPES
# ═══════════════════════════════════════════════════════════════════


class TestLiteralTypes:
    def test_literal_str(self):
        T = create_struct("T", {"v": (Literal["a", "b", "c"], ...)})
        assert zd_validate({"v": "a"}, T)["v"] == "a"

    def test_literal_rejects_invalid(self):
        T = create_struct("T", {"v": (Literal["a", "b"], ...)})
        with pytest.raises(ValidationError):
            zd_validate({"v": "z"}, T)

    def test_literal_int(self):
        T = create_struct("T", {"v": (Literal[1, 2, 3], ...)})
        assert zd_validate({"v": 2}, T)["v"] == 2


# ═══════════════════════════════════════════════════════════════════
# 7. ENUM HANDLING (via _resolve_enum)
# ═══════════════════════════════════════════════════════════════════


class TestEnumHandling:
    def test_str_enum_to_literal(self):
        class Color(str, Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

        resolved = _resolve_enum(Color)
        # Should produce Literal["red", "green", "blue"]
        assert resolved is not Color
        T = create_struct("T", {"v": (resolved, ...)})
        assert zd_validate({"v": "red"}, T)["v"] == "red"

    def test_int_enum_to_literal(self):
        class Priority(int, Enum):
            LOW = 1
            MED = 2
            HIGH = 3

        resolved = _resolve_enum(Priority)
        T = create_struct("T", {"v": (resolved, ...)})
        assert zd_validate({"v": 2}, T)["v"] == 2

    def test_non_enum_passthrough(self):
        assert _resolve_enum(str) is str
        assert _resolve_enum(int) is int

    def test_enum_schema_generation(self):
        class Status(str, Enum):
            ACTIVE = "active"
            INACTIVE = "inactive"

        def f(status: Status) -> None: ...

        schema = _zerodep_schema(f)
        prop = schema["properties"]["status"]
        assert set(prop["enum"]) == {"active", "inactive"}

    def test_enum_schema_parity(self):
        """Pydantic and zerodep should produce equivalent enum schemas."""

        class Mode(str, Enum):
            FAST = "fast"
            SLOW = "slow"

        def f(mode: Mode) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        # Both should have "mode" in properties
        assert "mode" in pd_schema["properties"]
        assert "mode" in zd_schema["properties"]

        # Both should have enum values (possibly via $ref or inline)
        pd_prop = pd_schema["properties"]["mode"]
        zd_prop = zd_schema["properties"]["mode"]

        if "$ref" in pd_prop:
            ref_name = pd_prop["$ref"].split("/")[-1]
            pd_enum = set(pd_schema["$defs"][ref_name]["enum"])
        else:
            pd_enum = set(pd_prop.get("enum", []))

        zd_enum = set(zd_prop.get("enum", []))
        assert pd_enum == zd_enum == {"fast", "slow"}


# ═══════════════════════════════════════════════════════════════════
# 8. ANNOTATED CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════


class TestAnnotatedConstraints:
    """Test constraint translation from Pydantic Field → zerodep."""

    def test_pydantic_field_ge_translates(self):
        ann = Annotated[int, Field(ge=0)]
        translated = _translate_annotated_metadata(ann)
        T = create_struct("T", {"v": (translated, ...)})
        assert zd_validate({"v": 5}, T)["v"] == 5
        with pytest.raises(ValidationError):
            zd_validate({"v": -1}, T)

    def test_pydantic_field_le_translates(self):
        ann = Annotated[int, Field(le=100)]
        translated = _translate_annotated_metadata(ann)
        T = create_struct("T", {"v": (translated, ...)})
        assert zd_validate({"v": 50}, T)["v"] == 50
        with pytest.raises(ValidationError):
            zd_validate({"v": 101}, T)

    def test_pydantic_field_max_length_translates(self):
        ann = Annotated[str, Field(max_length=5)]
        translated = _translate_annotated_metadata(ann)
        T = create_struct("T", {"v": (translated, ...)})
        assert zd_validate({"v": "abc"}, T)["v"] == "abc"
        with pytest.raises(ValidationError):
            zd_validate({"v": "toolregistry"}, T)

    def test_pydantic_field_description_translates(self):
        ann = Annotated[str, Field(description="A name")]
        translated = _translate_annotated_metadata(ann)
        schema = zd_json_schema(translated)
        assert schema["description"] == "A name"

    def test_native_zerodep_constraints_passthrough(self):
        """zerodep's own Ge/Le/Doc should pass through unchanged."""
        ann = Annotated[int, Ge(0), Le(100)]
        translated = _translate_annotated_metadata(ann)
        T = create_struct("T", {"v": (translated, ...)})
        assert zd_validate({"v": 50}, T)["v"] == 50
        with pytest.raises(ValidationError):
            zd_validate({"v": -1}, T)
        with pytest.raises(ValidationError):
            zd_validate({"v": 101}, T)

    def test_constraint_schema_parity(self):
        """Ge(0) should produce minimum:0 in both engines."""

        def f(count: Annotated[int, Field(ge=0)]) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        pd_min = pd_schema["properties"]["count"].get("minimum")
        zd_min = zd_schema["properties"]["count"].get("minimum")
        assert pd_min == zd_min == 0

    def test_max_length_schema_parity(self):
        def f(name: Annotated[str, Field(max_length=10)]) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["properties"]["name"].get("maxLength") == 10
        assert zd_schema["properties"]["name"].get("maxLength") == 10

    def test_description_schema_parity(self):
        def f(x: Annotated[int, Field(description="The x")] = 0) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["properties"]["x"].get("description") == "The x"
        assert zd_schema["properties"]["x"].get("description") == "The x"


# ═══════════════════════════════════════════════════════════════════
# 9. SCHEMA STRUCTURE PARITY
# ═══════════════════════════════════════════════════════════════════


class TestSchemaParity:
    """Both engines should produce equivalent JSON Schema structures."""

    def test_simple_function_schema(self):
        def f(name: str, age: int) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["type"] == zd_schema["type"] == "object"
        assert set(pd_schema["properties"]) == set(zd_schema["properties"])
        assert set(pd_schema.get("required", [])) == set(zd_schema.get("required", []))

    def test_defaults_schema(self):
        def f(name: str, age: int = 30) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert "name" in pd_schema.get("required", [])
        assert "name" in zd_schema.get("required", [])
        assert "age" not in pd_schema.get("required", [])
        assert "age" not in zd_schema.get("required", [])

        pd_default = pd_schema["properties"]["age"].get("default")
        zd_default = zd_schema["properties"]["age"].get("default")
        assert pd_default == zd_default == 30

    def test_type_mapping(self):
        """Basic type → JSON Schema type mapping should match."""

        def f(
            s: str,
            i: int,
            fl: float,
            b: bool,
        ) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        for field in ("s", "i", "fl", "b"):
            assert (
                pd_schema["properties"][field]["type"]
                == zd_schema["properties"][field]["type"]
            ), (
                f"Mismatch for {field}: "
                f"pydantic={pd_schema['properties'][field]} "
                f"zerodep={zd_schema['properties'][field]}"
            )

    def test_list_schema(self):
        def f(items: list[str]) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["properties"]["items"]["type"] == "array"
        assert zd_schema["properties"]["items"]["type"] == "array"
        assert pd_schema["properties"]["items"]["items"]["type"] == "string"
        assert zd_schema["properties"]["items"]["items"]["type"] == "string"

    def test_dict_schema(self):
        def f(m: dict[str, int]) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["properties"]["m"]["type"] == "object"
        assert zd_schema["properties"]["m"]["type"] == "object"
        assert pd_schema["properties"]["m"]["additionalProperties"]["type"] == "integer"
        assert zd_schema["properties"]["m"]["additionalProperties"]["type"] == "integer"

    def test_literal_schema(self):
        def f(mode: Literal["a", "b"]) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["properties"]["mode"]["enum"] == ["a", "b"]
        assert zd_schema["properties"]["mode"]["enum"] == ["a", "b"]

    def test_union_schema(self):
        def f(v: Union[str, int]) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        pd_prop = pd_schema["properties"]["v"]
        zd_prop = zd_schema["properties"]["v"]

        pd_key = "anyOf" if "anyOf" in pd_prop else "oneOf"
        zd_key = "anyOf" if "anyOf" in zd_prop else "oneOf"

        pd_types = {b.get("type") for b in pd_prop[pd_key]}
        zd_types = {b.get("type") for b in zd_prop[zd_key]}
        assert pd_types == zd_types == {"string", "integer"}

    def test_optional_schema_after_simplify(self):
        """After simplification, str | None should be type: string."""

        def f(v: str | None = None) -> None: ...

        pd_schema = _simplify_nullable_schemas(_pydantic_schema(f))
        zd_schema = _zerodep_schema(f)  # already simplified

        assert pd_schema["properties"]["v"]["type"] == "string"
        assert zd_schema["properties"]["v"]["type"] == "string"


# ═══════════════════════════════════════════════════════════════════
# 10. REQUIRED / OPTIONAL FIELD TRACKING
# ═══════════════════════════════════════════════════════════════════


class TestRequiredOptional:
    def test_required_fields(self):
        T = create_struct("T", {"a": (str, ...), "b": (int, ...)})
        schema = zd_json_schema(T)
        assert set(schema["required"]) == {"a", "b"}

    def test_optional_fields_not_required(self):
        T = create_struct("T", {"a": (str, ...), "b": (int, 42)})
        schema = zd_json_schema(T)
        assert "a" in schema["required"]
        assert "b" not in schema.get("required", [])

    def test_missing_required_field_fails(self):
        T = create_struct("T", {"a": (str, ...), "b": (int, ...)})
        with pytest.raises(ValidationError):
            zd_validate({"a": "hello"}, T)

    def test_missing_optional_field_ok(self):
        T = create_struct("T", {"a": (str, ...), "b": (int, 42)})
        r = zd_validate({"a": "hello"}, T)
        assert r["a"] == "hello"


# ═══════════════════════════════════════════════════════════════════
# 11. NESTED STRUCTS
# ═══════════════════════════════════════════════════════════════════


class TestNestedStructs:
    def test_nested_typeddict(self):
        Inner = create_struct("Inner", {"x": (int, ...), "y": (str, ...)})
        Outer = create_struct("Outer", {"inner": (Inner, ...), "label": (str, ...)})
        r = zd_validate({"inner": {"x": 1, "y": "two"}, "label": "test"}, Outer)
        assert r["inner"]["x"] == 1
        assert r["label"] == "test"

    def test_nested_dataclass(self):
        @dataclass
        class Point:
            x: int
            y: int

        T = create_struct("T", {"point": (Point, ...)})
        r = zd_validate({"point": {"x": 1, "y": 2}}, T)
        assert r["point"]["x"] == 1

    def test_nested_schema_inline(self):
        """zerodep inlines nested struct schemas (no $ref/$defs)."""
        Inner = create_struct("Inner", {"value": (int, ...)})
        Outer = create_struct("Outer", {"inner": (Inner, ...)})
        schema = zd_json_schema(Outer)
        prop = schema["properties"]["inner"]
        assert "properties" in prop
        assert "value" in prop["properties"]
        assert "$ref" not in prop

    def test_deeply_nested(self):
        L3 = create_struct("L3", {"val": (str, ...)})
        L2 = create_struct("L2", {"l3": (L3, ...)})
        L1 = create_struct("L1", {"l2": (L2, ...)})
        r = zd_validate({"l2": {"l3": {"val": "deep"}}}, L1)
        assert r["l2"]["l3"]["val"] == "deep"


# ═══════════════════════════════════════════════════════════════════
# 12. ANY TYPE
# ═══════════════════════════════════════════════════════════════════


class TestAnyType:
    def test_any_accepts_anything(self):
        T = create_struct("T", {"v": (Any, ...)})
        assert zd_validate({"v": "str"}, T)["v"] == "str"
        assert zd_validate({"v": 42}, T)["v"] == 42
        assert zd_validate({"v": [1, 2]}, T)["v"] == [1, 2]
        assert zd_validate({"v": None}, T)["v"] is None

    def test_any_schema_is_empty(self):
        T = create_struct("T", {"v": (Any, ...)})
        schema = zd_json_schema(T)
        assert schema["properties"]["v"] == {}


# ═══════════════════════════════════════════════════════════════════
# 13. DEFAULT VALUES IN SCHEMA
# ═══════════════════════════════════════════════════════════════════


class TestDefaults:
    def test_default_in_schema(self):
        T = create_struct("T", {"v": (int, 42)})
        schema = zd_json_schema(T)
        assert schema["properties"]["v"]["default"] == 42

    def test_default_none_in_schema(self):
        T = create_struct("T", {"v": (str | None, None)})
        schema = zd_json_schema(T)
        assert schema["properties"]["v"]["default"] is None

    def test_no_default_for_required(self):
        T = create_struct("T", {"v": (int, ...)})
        schema = zd_json_schema(T)
        assert "default" not in schema["properties"]["v"]

    def test_default_parity(self):
        """Default values in schema should match between engines."""

        def f(x: int = 10, y: str = "hello") -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_schema = _zerodep_schema(f)

        assert pd_schema["properties"]["x"]["default"] == 10
        assert zd_schema["properties"]["x"]["default"] == 10
        assert pd_schema["properties"]["y"]["default"] == "hello"
        assert zd_schema["properties"]["y"]["default"] == "hello"


# ═══════════════════════════════════════════════════════════════════
# 14. _simplify_nullable_schemas
# ═══════════════════════════════════════════════════════════════════


class TestSimplifyNullable:
    def test_pydantic_anyof_pattern(self):
        """anyOf: [{type: str}, {type: null}] → type: str."""
        schema = {
            "properties": {"v": {"anyOf": [{"type": "string"}, {"type": "null"}]}}
        }
        result = _simplify_nullable_schemas(schema)
        assert result["properties"]["v"] == {"type": "string"}

    def test_zerodep_type_array_pattern(self):
        """type: ["string", "null"] → type: "string"."""
        schema = {"properties": {"v": {"type": ["string", "null"]}}}
        result = _simplify_nullable_schemas(schema)
        assert result["properties"]["v"] == {"type": "string"}

    def test_multi_type_anyof(self):
        """anyOf with 3+ types: strip only null."""
        schema = {
            "properties": {
                "v": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "integer"},
                        {"type": "null"},
                    ]
                }
            }
        }
        result = _simplify_nullable_schemas(schema)
        assert result["properties"]["v"]["anyOf"] == [
            {"type": "string"},
            {"type": "integer"},
        ]

    def test_no_null_untouched(self):
        """No null variant → unchanged."""
        schema = {
            "properties": {"v": {"anyOf": [{"type": "string"}, {"type": "integer"}]}}
        }
        result = _simplify_nullable_schemas(schema)
        assert result["properties"]["v"]["anyOf"] == [
            {"type": "string"},
            {"type": "integer"},
        ]


# ═══════════════════════════════════════════════════════════════════
# 15. ERROR REPORTING
# ═══════════════════════════════════════════════════════════════════


class TestErrorReporting:
    def test_error_has_path(self):
        T = create_struct("T", {"name": (str, ...), "age": (int, ...)})
        with pytest.raises(ValidationError) as exc_info:
            zd_validate({"name": 123, "age": "bad"}, T)
        paths = {e.path for e in exc_info.value.errors}
        assert "name" in paths
        assert "age" in paths

    def test_nested_error_path(self):
        Inner = create_struct("Inner", {"x": (int, ...)})
        Outer = create_struct("Outer", {"inner": (Inner, ...)})
        with pytest.raises(ValidationError) as exc_info:
            zd_validate({"inner": {"x": "bad"}}, Outer)
        paths = {e.path for e in exc_info.value.errors}
        assert "inner.x" in paths

    def test_missing_required_error(self):
        T = create_struct("T", {"a": (str, ...), "b": (int, ...)})
        with pytest.raises(ValidationError) as exc_info:
            zd_validate({}, T)
        assert len(exc_info.value.errors) == 2


# ═══════════════════════════════════════════════════════════════════
# 16. KNOWN BEHAVIORAL DIFFERENCES (DOCUMENTED)
# ═══════════════════════════════════════════════════════════════════


class TestKnownDifferences:
    """Differences between Pydantic and zerodep that are accepted."""

    def test_zerodep_does_not_fill_defaults(self):
        """zerodep validates but does NOT fill in default values."""
        T = create_struct("T", {"a": (str, ...), "b": (int, 42)})
        r = zd_validate({"a": "hello"}, T)
        assert "b" not in r  # zerodep: missing optional → absent

    def test_pydantic_fills_defaults(self):
        """Pydantic fills in defaults — this is a known difference."""
        M = create_model("M", a=(str, ...), b=(int, 42), __base__=_PydanticBase)
        m = M(a="hello")
        assert m.b == 42  # Pydantic fills it in

    def test_zerodep_no_str_to_bool_coercion(self):
        """Pydantic coerces 'true'→True; zerodep does not."""
        T = create_struct("T", {"v": (bool, ...)})
        with pytest.raises(ValidationError):
            zd_validate({"v": "true"}, T, coerce=True)

        M = create_model("M", v=(bool, ...), __base__=_PydanticBase)
        assert M(v="true").v is True  # Pydantic does coerce

    def test_zerodep_returns_dict_not_object(self):
        """zerodep returns plain dict, not an object with attributes."""
        T = create_struct("T", {"name": (str, ...)})
        r = zd_validate({"name": "test"}, T)
        assert isinstance(r, dict)
        assert r["name"] == "test"

    def test_schema_inlines_vs_ref(self):
        """zerodep inlines nested schemas; Pydantic uses $ref/$defs."""
        Inner = create_struct("Inner", {"x": (int, ...)})
        Outer = create_struct("Outer", {"inner": (Inner, ...)})
        schema = zd_json_schema(Outer)
        assert "$defs" not in schema
        assert "$ref" not in schema["properties"]["inner"]

    def test_nullable_representation_differs(self):
        """Pydantic: anyOf; zerodep: type array. Both simplified equally."""

        def f(v: str | None = None) -> None: ...

        pd_schema = _pydantic_schema(f)
        zd_raw = _zerodep_schema(f)

        # Pydantic raw uses anyOf
        pd_prop = pd_schema["properties"]["v"]
        assert "anyOf" in pd_prop

        # zerodep raw uses type array — but _zerodep_schema already simplifies
        zd_prop = zd_raw["properties"]["v"]
        assert zd_prop["type"] == "string"  # simplified

        # After simplification, both match
        pd_simplified = _simplify_nullable_schemas(pd_schema)
        assert pd_simplified["properties"]["v"]["type"] == "string"


# ═══════════════════════════════════════════════════════════════════
# 17. END-TO-END TOOL REGISTRATION FLOW
# ═══════════════════════════════════════════════════════════════════


class TestEndToEnd:
    """Test the full tool registration → validate → execute flow."""

    def test_simple_function_roundtrip(self):
        from toolregistry import Tool

        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        tool = Tool.from_function(add)
        assert tool.parameters["properties"]["a"]["type"] == "integer"
        result = tool.run({"a": 3, "b": 4})
        assert result == 7

    def test_coercion_roundtrip(self):
        """LLM sends strings → coerce → correct types for execution."""
        from toolregistry import Tool

        def multiply(x: int, y: float) -> float:
            """Multiply."""
            return x * y

        tool = Tool.from_function(multiply)
        result = tool.run({"x": "3", "y": "2.5"})
        assert result == 7.5

    def test_complex_function_roundtrip(self):
        from toolregistry import Tool

        class Priority(str, Enum):
            LOW = "low"
            HIGH = "high"

        def process(
            name: str,
            tags: list[str],
            priority: Priority = Priority.LOW,
            count: Annotated[int, Ge(0)] = 0,
            mode: Literal["fast", "slow"] = "fast",
        ) -> dict:
            """Process."""
            return {"name": name, "tags": tags}

        tool = Tool.from_function(process)
        schema = tool.parameters
        assert "name" in schema["properties"]
        assert "tags" in schema["properties"]
        assert "priority" in schema["properties"]

        result = tool.run({"name": "test", "tags": ["a", "b"], "priority": "high"})
        assert result == {"name": "test", "tags": ["a", "b"]}

    def test_kwargs_function_roundtrip(self):
        from toolregistry import Tool

        def flexible(x: int, **kwargs) -> dict:
            """Accept extra args."""
            return {"x": x, **kwargs}

        tool = Tool.from_function(flexible)
        assert tool.parameters.get("additionalProperties") is True
        result = tool.run({"x": 1, "extra": "value"})
        assert result == {"x": 1, "extra": "value"}

    def test_optional_param_roundtrip(self):
        from toolregistry import Tool

        def greet(name: str, greeting: str | None = None) -> str:
            """Greet."""
            return f"{greeting or 'Hello'}, {name}!"

        tool = Tool.from_function(greet)
        assert tool.run({"name": "World"}) == "Hello, World!"
        assert tool.run({"name": "World", "greeting": "Hi"}) == "Hi, World!"
