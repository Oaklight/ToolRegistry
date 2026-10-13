"""Tests for ToolTag, ToolMetadata, and Tool.metadata integration."""

import dataclasses
from pathlib import Path

import pytest

from toolregistry import Tool, ToolMetadata, ToolRegistry, ToolTag
from toolregistry.config import (
    ConfigError,
    ToolMetadataOverride,
    load_config,
    save_config,
)


# ---------------------------------------------------------------------------
# ToolTag
# ---------------------------------------------------------------------------


class TestToolTag:
    def test_str_equality(self):
        """ToolTag members compare equal to their string values."""
        assert ToolTag.READ_ONLY == "read_only"
        assert ToolTag.DESTRUCTIVE == "destructive"

    def test_membership_in_string_set(self):
        tags = {"read_only", "network"}
        assert ToolTag.READ_ONLY in tags
        assert ToolTag.NETWORK in tags
        assert ToolTag.SLOW not in tags


# ---------------------------------------------------------------------------
# ToolMetadata
# ---------------------------------------------------------------------------


class TestToolMetadata:
    def test_defaults(self):
        m = ToolMetadata()
        assert m.is_async is False
        assert m.is_concurrency_safe is True
        assert m.timeout is None
        assert m.locality == "any"
        assert m.tags == set()
        assert m.custom_tags == set()
        assert m.extra == {}

    def test_all_tags_union(self):
        m = ToolMetadata(
            tags={ToolTag.READ_ONLY, ToolTag.NETWORK},
            custom_tags={"my_custom", "another"},
        )
        assert m.all_tags == {"read_only", "network", "my_custom", "another"}

    def test_all_tags_empty(self):
        assert ToolMetadata().all_tags == set()

    def test_locality_values(self):
        for val in ("local", "remote", "any"):
            m = ToolMetadata(locality=val)
            assert m.locality == val

    def test_locality_invalid(self):
        import pytest

        with pytest.raises(Exception):
            ToolMetadata(locality="cloud")

    def test_extra_arbitrary_data(self):
        m = ToolMetadata(extra={"author": "alice", "version": 2})
        assert m.extra["author"] == "alice"

    def test_replace_preserves_tags(self):
        import dataclasses

        m = ToolMetadata(tags={ToolTag.SLOW}, timeout=10.0)
        m2 = dataclasses.replace(m, is_async=True)
        assert m2.is_async is True
        assert m2.tags == {ToolTag.SLOW}
        assert m2.timeout == 10.0


# ---------------------------------------------------------------------------
# Tool.metadata integration
# ---------------------------------------------------------------------------


def _sync_func(x: int) -> int:
    """Add one."""
    return x + 1


async def _async_func(x: int) -> int:
    """Async add one."""
    return x + 1


class TestToolMetadataIntegration:
    def test_from_function_default_metadata(self):
        tool = Tool.from_function(_sync_func)
        assert isinstance(tool.metadata, ToolMetadata)
        assert tool.metadata.is_async is False
        assert tool.is_async is False

    def test_from_function_async_detection(self):
        tool = Tool.from_function(_async_func)
        assert tool.metadata.is_async is True
        assert tool.is_async is True

    def test_from_function_custom_metadata(self):
        meta = ToolMetadata(
            tags={ToolTag.NETWORK, ToolTag.SLOW},
            timeout=30.0,
            custom_tags={"api"},
            locality="remote",
        )
        tool = Tool.from_function(_sync_func, metadata=meta)
        assert tool.metadata.tags == {ToolTag.NETWORK, ToolTag.SLOW}
        assert tool.metadata.timeout == 30.0
        assert tool.metadata.locality == "remote"
        assert "api" in tool.metadata.custom_tags
        # is_async should be auto-detected (False), even if metadata said True
        assert tool.is_async is False

    def test_from_function_async_overrides_metadata(self):
        """is_async in metadata is always overridden by auto-detection."""
        meta = ToolMetadata(is_async=False)
        tool = Tool.from_function(_async_func, metadata=meta)
        assert tool.is_async is True

    def test_backward_compat_is_async_kwarg(self):
        """Legacy Tool(..., is_async=True) still works via model_validator."""
        tool = Tool(
            name="test",
            description="test",
            parameters={},
            callable=_sync_func,
            is_async=True,
        )
        assert tool.is_async is True
        assert tool.metadata.is_async is True

    def test_backward_compat_is_async_false(self):
        tool = Tool(
            name="test",
            description="test",
            parameters={},
            callable=_sync_func,
            is_async=False,
        )
        assert tool.is_async is False

    def test_metadata_kwarg_takes_precedence_over_is_async(self):
        """When both metadata and is_async are passed, metadata wins."""
        tool = Tool(
            name="test",
            description="test",
            parameters={},
            callable=_sync_func,
            is_async=False,
            metadata=ToolMetadata(is_async=True),
        )
        # metadata is explicitly provided, so its is_async should be used
        assert tool.is_async is True

    def test_default_metadata_when_no_is_async(self):
        tool = Tool(
            name="test",
            description="test",
            parameters={},
            callable=_sync_func,
        )
        assert tool.is_async is False
        assert isinstance(tool.metadata, ToolMetadata)


# ---------------------------------------------------------------------------
# Execution hints (issue #280)
# ---------------------------------------------------------------------------


class TestExecutionHints:
    """Tri-state execution hints on ToolMetadata and the resolved accessor."""

    def test_defaults_unset_and_accessor_empty(self):
        m = ToolMetadata()
        assert m.title is None
        assert m.read_only_hint is None
        assert m.destructive_hint is None
        assert m.idempotent_hint is None
        assert m.open_world_hint is None
        assert m.execution_hints == {}

    def test_explicit_true_and_false_preserved(self):
        m = ToolMetadata(
            title="My Tool",
            read_only_hint=False,
            destructive_hint=True,
            idempotent_hint=False,
            open_world_hint=True,
        )
        assert m.execution_hints == {
            "title": "My Tool",
            "read_only_hint": False,
            "destructive_hint": True,
            "idempotent_hint": False,
            "open_world_hint": True,
        }

    def test_false_is_distinguishable_from_unset(self):
        unset = ToolMetadata()
        explicit_false = ToolMetadata(read_only_hint=False)
        assert "read_only_hint" not in unset.execution_hints
        assert explicit_false.execution_hints["read_only_hint"] is False
        assert isinstance(explicit_false.read_only_hint, bool)

    def test_read_only_hint_derived_from_tag_when_unset(self):
        m = ToolMetadata(tags={ToolTag.READ_ONLY})
        assert m.execution_hints == {"read_only_hint": True}

    def test_destructive_hint_derived_from_tag_when_unset(self):
        m = ToolMetadata(tags={ToolTag.DESTRUCTIVE})
        assert m.execution_hints == {"destructive_hint": True}

    def test_explicit_hint_overrides_tag(self):
        # Explicit False beats a READ_ONLY tag.
        assert ToolMetadata(
            read_only_hint=False, tags={ToolTag.READ_ONLY}
        ).execution_hints == {"read_only_hint": False}
        # Explicit False beats a DESTRUCTIVE tag.
        assert ToolMetadata(
            destructive_hint=False, tags={ToolTag.DESTRUCTIVE}
        ).execution_hints == {"destructive_hint": False}
        # Explicit True wins without any tag.
        assert ToolMetadata(read_only_hint=True).execution_hints == {
            "read_only_hint": True
        }

    def test_non_deriving_tags_do_not_imply_hints(self):
        m = ToolMetadata(
            tags={
                ToolTag.NETWORK,
                ToolTag.FILE_SYSTEM,
                ToolTag.PRIVILEGED,
                ToolTag.SLOW,
            }
        )
        assert m.execution_hints == {}
        assert m.idempotent_hint is None
        assert m.open_world_hint is None

    def test_accessor_keys_are_snake_case_field_names(self):
        m = ToolMetadata(tags={ToolTag.READ_ONLY}, title="t", open_world_hint=True)
        assert set(m.execution_hints) == {"title", "read_only_hint", "open_world_hint"}
        field_names = {f.name for f in dataclasses.fields(ToolMetadata)}
        for key in m.execution_hints:
            assert key in field_names
            assert key == key.lower()
        assert "readOnlyHint" not in m.execution_hints

    def test_copy_and_replace_round_trip_preserves_hints(self):
        m = ToolMetadata(
            title="T",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
        assert dataclasses.replace(m, timeout=5.0).execution_hints == m.execution_hints
        assert (
            m.model_copy(update={"timeout": 9.0}).execution_hints == m.execution_hints
        )

    def test_model_dump_includes_hint_fields(self):
        d = ToolMetadata(title="T", read_only_hint=False).model_dump()
        assert d["title"] == "T"
        assert d["read_only_hint"] is False
        assert d["destructive_hint"] is None
        assert d["idempotent_hint"] is None
        assert d["open_world_hint"] is None

    def test_tool_proxy_exposes_resolved_hints(self):
        tool = Tool.from_function(
            _sync_func, metadata=ToolMetadata(tags={ToolTag.READ_ONLY}, title="G")
        )
        assert tool.execution_hints == {"title": "G", "read_only_hint": True}

    def test_tool_replace_and_refresh_preserve_hints(self):
        tool = Tool.from_function(
            _sync_func, metadata=ToolMetadata(title="T", read_only_hint=True)
        )
        assert tool.with_refreshed_at("2026-01-01T00:00:00Z").execution_hints == {
            "title": "T",
            "read_only_hint": True,
        }
        assert tool.update_namespace("ns").execution_hints == {
            "title": "T",
            "read_only_hint": True,
        }

    def test_generated_schema_unaffected_by_hints(self):
        plain = Tool.from_function(_sync_func)
        hinted = Tool.from_function(
            _sync_func,
            metadata=ToolMetadata(
                title="T",
                read_only_hint=True,
                destructive_hint=True,
                idempotent_hint=True,
                open_world_hint=True,
            ),
        )
        # Setting any hint must not leak into the provider schema.
        assert plain.get_schema() == hinted.get_schema()
        rendered = str(hinted.get_schema())
        for leaked in ("readOnlyHint", "read_only_hint", "title"):
            assert leaked not in rendered

    def test_schema_hash_unaffected_by_hints(self):
        plain = Tool.from_function(_sync_func)
        hinted = Tool.from_function(
            _sync_func, metadata=ToolMetadata(read_only_hint=True, title="T")
        )
        assert plain.metadata.schema_hash == hinted.metadata.schema_hash

    def test_runtime_update_and_namespace_update_accept_hints(self):
        reg = ToolRegistry()
        reg.register(_sync_func)
        name = reg.list_tools()[0]
        reg.update_tool_metadata(name, read_only_hint=False, title="Runtime")
        tool = reg.get_tool(name)
        assert tool.execution_hints == {"title": "Runtime", "read_only_hint": False}
        assert tool.metadata.read_only_hint is False

        # Namespace-wide update also accepts the hint fields.
        reg2 = ToolRegistry()
        reg2.register(_sync_func, namespace="ns")
        name2 = reg2.list_tools()[0]
        reg2.update_namespace_metadata("ns", open_world_hint=True)
        assert reg2.get_tool(name2).execution_hints == {"open_world_hint": True}


class TestExecutionHintsConfigOverride:
    """Hints survive config overrides, loader parsing, and registry apply."""

    def test_apply_metadata_config_with_override_object(self):
        reg = ToolRegistry()
        reg.register(_sync_func)
        name = reg.list_tools()[0]
        reg.apply_metadata_config(
            {name: ToolMetadataOverride(title="Add", read_only_hint=True)}
        )
        assert reg.get_tool(name).execution_hints == {
            "title": "Add",
            "read_only_hint": True,
        }

    def test_apply_metadata_config_with_plain_dict(self):
        reg = ToolRegistry()
        reg.register(_sync_func)
        name = reg.list_tools()[0]
        reg.apply_metadata_config(
            {name: {"read_only_hint": False, "idempotent_hint": True}}
        )
        assert reg.get_tool(name).execution_hints == {
            "read_only_hint": False,
            "idempotent_hint": True,
        }

    def test_apply_metadata_config_unset_keeps_tag_derived_hint(self):
        reg = ToolRegistry()
        reg.register(
            Tool.from_function(
                _sync_func, metadata=ToolMetadata(tags={ToolTag.READ_ONLY})
            )
        )
        name = reg.list_tools()[0]
        # Only title is overridden; the READ_ONLY tag still derives read_only.
        reg.apply_metadata_config({name: ToolMetadataOverride(title="T")})
        assert reg.get_tool(name).execution_hints == {
            "title": "T",
            "read_only_hint": True,
        }

    def test_loader_parses_and_round_trips_hints(self, tmp_path: Path):
        p = tmp_path / "tools.json"
        p.write_text(
            '{"mode":"denylist","tool_metadata":{"x":{'
            '"title":"T","read_only_hint":false,"open_world_hint":true}}}',
            encoding="utf-8",
        )
        override = load_config(p).tool_metadata["x"]
        assert override.title == "T"
        assert override.read_only_hint is False
        assert override.open_world_hint is True
        assert override.destructive_hint is None
        assert override.to_dict() == {
            "title": "T",
            "read_only_hint": False,
            "open_world_hint": True,
        }

        save_config(load_config(p), p)
        reloaded = load_config(p).tool_metadata["x"]
        assert reloaded.title == "T"
        assert reloaded.read_only_hint is False
        assert reloaded.open_world_hint is True

    def test_loader_rejects_non_bool_hint(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text(
            '{"mode":"denylist","tool_metadata":{"x":{"read_only_hint":"yes"}}}',
            encoding="utf-8",
        )
        with pytest.raises(ConfigError):
            load_config(p)

    def test_loader_rejects_non_string_title(self, tmp_path: Path):
        p = tmp_path / "bad2.json"
        p.write_text(
            '{"mode":"denylist","tool_metadata":{"x":{"title":5}}}', encoding="utf-8"
        )
        with pytest.raises(ConfigError):
            load_config(p)


class TestExecutionHintsSerialization:
    """Hints appear in registry status and admin detail payloads."""

    def test_get_tools_status_exposes_resolved_hints(self):
        reg = ToolRegistry()
        reg.register(
            Tool.from_function(
                _sync_func, metadata=ToolMetadata(tags={ToolTag.READ_ONLY})
            )
        )
        status = reg.get_tools_status()[0]
        assert status["execution_hints"] == {"read_only_hint": True}

    def test_get_tools_status_empty_when_unset(self):
        reg = ToolRegistry()
        reg.register(_sync_func)
        assert reg.get_tools_status()[0]["execution_hints"] == {}
