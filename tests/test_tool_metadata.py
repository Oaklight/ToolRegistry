"""Tests for ToolTag, ToolMetadata, and Tool.metadata integration."""

from toolregistry import Tool, ToolMetadata, ToolTag


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

    def test_model_copy_preserves_tags(self):
        m = ToolMetadata(tags={ToolTag.SLOW}, timeout=10.0)
        m2 = m.model_copy(update={"is_async": True})
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
