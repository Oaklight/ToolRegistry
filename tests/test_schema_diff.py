"""Tests for schema change classification."""

from toolregistry.schema_diff import SchemaChangeKind, classify_schema_change


class TestClassifySchemaChange:
    """Test classify_schema_change heuristics."""

    def test_identical_schemas(self):
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        kind, summary = classify_schema_change(schema, schema)
        assert kind == SchemaChangeKind.COMPATIBLE
        assert summary == {}

    def test_added_optional_parameter(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.COMPATIBLE
        assert summary == {"added_optional": ["b"]}

    def test_added_required_parameter_is_breaking(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.BREAKING
        assert summary["added_required"] == ["b"]

    def test_removed_parameter_is_breaking(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.BREAKING
        assert summary["removed"] == ["b"]

    def test_newly_required_is_breaking(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.BREAKING
        assert summary["newly_required"] == ["b"]

    def test_no_longer_required_is_compatible(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            "required": ["a"],
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.COMPATIBLE
        assert summary["no_longer_required"] == ["b"]

    def test_type_change_is_breaking(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "integer"}},
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.BREAKING
        assert summary["type_changed"] == {"a": {"old": "string", "new": "integer"}}

    def test_multiple_changes_mixed(self):
        old = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "integer"},
            },
            "required": ["a"],
        }
        new = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "c": {"type": "boolean"},
            },
            "required": ["a", "c"],
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.BREAKING
        assert "b" in summary["removed"]
        assert "c" in summary["added_required"]

    def test_empty_schemas(self):
        kind, summary = classify_schema_change({}, {})
        assert kind == SchemaChangeKind.COMPATIBLE
        assert summary == {}

    def test_toolcall_reason_ignored(self):
        old = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "toolcall_reason": {"type": "string"},
            },
        }
        new = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
            },
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.COMPATIBLE
        assert summary == {}

    def test_anyof_type_change(self):
        old = {
            "type": "object",
            "properties": {
                "a": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            },
        }
        new = {
            "type": "object",
            "properties": {
                "a": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.BREAKING
        assert "a" in summary["type_changed"]


class TestSchemaChangeKindEnum:
    def test_values(self):
        assert SchemaChangeKind.COMPATIBLE == "compatible"
        assert SchemaChangeKind.BREAKING == "breaking"
        assert SchemaChangeKind.UNKNOWN == "unknown"

    def test_is_str(self):
        assert isinstance(SchemaChangeKind.COMPATIBLE, str)
