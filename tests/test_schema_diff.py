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

    def test_toolcall_reason_treated_as_normal_param(self):
        """toolcall_reason is no longer special — removing it is a real change."""
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
        assert kind == SchemaChangeKind.BREAKING
        assert "toolcall_reason" in summary["removed"]

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

    def test_no_structural_overlap_returns_unknown(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        }
        new = {
            "type": "object",
            "properties": {"x": {"type": "string"}, "y": {"type": "integer"}},
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.UNKNOWN
        assert "added" in summary
        assert "removed" in summary

    def test_partial_overlap_not_unknown(self):
        old = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
        }
        new = {
            "type": "object",
            "properties": {"a": {"type": "string"}, "c": {"type": "boolean"}},
        }
        kind, summary = classify_schema_change(old, new)
        assert kind != SchemaChangeKind.UNKNOWN

    def test_anyof_order_independent(self):
        """json.dumps(sort_keys=True) makes sub-schema comparison order-independent."""
        old = {
            "type": "object",
            "properties": {
                "a": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]},
            },
        }
        new = {
            "type": "object",
            "properties": {
                "a": {"anyOf": [{"type": "null"}, {"minLength": 1, "type": "string"}]},
            },
        }
        kind, summary = classify_schema_change(old, new)
        assert kind == SchemaChangeKind.COMPATIBLE
        assert "type_changed" not in summary


class TestToolcallReasonHashExclusion:
    """toolcall_reason is no longer injected into parameters, so hash treats it normally."""

    def test_hash_includes_toolcall_reason_when_present(self):
        from toolregistry.utils import compute_schema_hash

        schema_with = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "toolcall_reason": {"type": "string", "description": "Why"},
            },
        }
        schema_without = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
            },
        }
        assert compute_schema_hash(schema_with) != compute_schema_hash(schema_without)

    def test_hash_still_sensitive_to_real_changes(self):
        from toolregistry.utils import compute_schema_hash

        s1 = {
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "toolcall_reason": {"type": "string"},
            },
        }
        s2 = {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "toolcall_reason": {"type": "string"},
            },
        }
        assert compute_schema_hash(s1) != compute_schema_hash(s2)
