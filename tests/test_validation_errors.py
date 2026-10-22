"""The public validation error types are the ones actually raised."""

import pytest

from toolregistry import (
    VALIDATION_ERRORS,
    ErrorDetail,
    SchemaErrorDetail,
    SchemaValidationError,
    Tool,
    ValidationError,
)
from toolregistry._vendor import jsonschema as vendor_jsonschema
from toolregistry._vendor import validate as vendor_validate


def _tool() -> Tool:
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    return Tool.from_function(add)


class TestExportedTypes:
    def test_exports_are_the_vendored_classes(self):
        # Identity, not equality: an upstream vendor update that swaps the
        # class would otherwise change what callers catch without a notice.
        assert ValidationError is vendor_validate.ValidationError
        assert ErrorDetail is vendor_validate.ErrorDetail
        assert SchemaValidationError is vendor_jsonschema.SchemaValidationError
        assert SchemaErrorDetail is vendor_jsonschema.SchemaErrorDetail

    def test_the_tuple_catches_both_failures(self):
        # The two classes share no base, so the tuple is the documented way
        # to map either failure to one outcome (#342).
        assert VALIDATION_ERRORS == (ValidationError, SchemaValidationError)

        tool = _tool()
        with pytest.raises(VALIDATION_ERRORS):
            tool.validate_parameters({"a": "not-a-number", "b": 1})

        schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
        with pytest.raises(VALIDATION_ERRORS):
            vendor_jsonschema.schema_validate({"a": "x"}, schema)

    def test_validate_parameters_raises_the_exported_type(self):
        tool = _tool()

        with pytest.raises(ValidationError) as excinfo:
            tool.validate_parameters({"a": "not-a-number", "b": 1})

        assert excinfo.value.errors
        detail = excinfo.value.errors[0]
        assert isinstance(detail, ErrorDetail)
        assert detail.message

    def test_schema_validation_raises_the_exported_type(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
            "required": ["a"],
        }

        with pytest.raises(SchemaValidationError) as excinfo:
            vendor_jsonschema.schema_validate({"a": "x"}, schema)

        assert excinfo.value.errors
        assert isinstance(excinfo.value.errors[0], SchemaErrorDetail)
