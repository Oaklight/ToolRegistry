"""Tests for the permission handler system (types, protocols, registry integration)."""

import asyncio

from toolregistry import (
    PermissionHandler,
    AsyncPermissionHandler,
    PermissionRequest,
    PermissionResult,
    ToolMetadata,
    ToolRegistry,
    ToolTag,
)
from toolregistry.events import ChangeEventType


# ---------------------------------------------------------------------------
# PermissionResult
# ---------------------------------------------------------------------------


class TestPermissionResult:
    def test_values(self):
        assert PermissionResult.ALLOW == "allow"
        assert PermissionResult.DENY == "deny"
        assert PermissionResult.ASK == "ask"

    def test_members(self):
        assert set(PermissionResult) == {
            PermissionResult.ALLOW,
            PermissionResult.DENY,
            PermissionResult.ASK,
        }


# ---------------------------------------------------------------------------
# PermissionRequest
# ---------------------------------------------------------------------------


class TestPermissionRequest:
    def test_defaults(self):
        req = PermissionRequest(tool_name="my_tool")
        assert req.tool_name == "my_tool"
        assert req.parameters == {}
        assert req.reason == ""
        assert req.rule_name == ""
        assert isinstance(req.metadata, ToolMetadata)

    def test_full_construction(self):
        meta = ToolMetadata(tags={ToolTag.DESTRUCTIVE}, timeout=10.0)
        req = PermissionRequest(
            tool_name="delete_file",
            parameters={"path": "/tmp/foo"},
            reason="Tool is destructive",
            rule_name="ask_destructive",
            metadata=meta,
        )
        assert req.tool_name == "delete_file"
        assert req.parameters == {"path": "/tmp/foo"}
        assert req.reason == "Tool is destructive"
        assert req.rule_name == "ask_destructive"
        assert ToolTag.DESTRUCTIVE in req.metadata.tags


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class AlwaysAllowHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        return PermissionResult.ALLOW


class AlwaysDenyHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        return PermissionResult.DENY


class AsyncAlwaysAllowHandler:
    async def handle(self, request: PermissionRequest) -> PermissionResult:
        return PermissionResult.ALLOW


class TestProtocolConformance:
    def test_sync_handler_isinstance(self):
        assert isinstance(AlwaysAllowHandler(), PermissionHandler)

    def test_async_handler_isinstance(self):
        assert isinstance(AsyncAlwaysAllowHandler(), AsyncPermissionHandler)

    def test_sync_handler_invoke(self):
        handler = AlwaysAllowHandler()
        result = handler.handle(PermissionRequest(tool_name="test"))
        assert result == PermissionResult.ALLOW

    def test_async_handler_invoke(self):
        handler = AsyncAlwaysAllowHandler()
        result = asyncio.run(handler.handle(PermissionRequest(tool_name="test")))
        assert result == PermissionResult.ALLOW


# ---------------------------------------------------------------------------
# ToolRegistry permission handler integration
# ---------------------------------------------------------------------------


class TestRegistryPermissionHandler:
    def test_no_handler_by_default(self):
        reg = ToolRegistry()
        assert reg.get_permission_handler() is None

    def test_default_fallback_is_deny(self):
        reg = ToolRegistry()
        assert reg.permission_fallback == PermissionResult.DENY

    def test_set_sync_handler(self):
        reg = ToolRegistry()
        handler = AlwaysAllowHandler()
        reg.set_permission_handler(handler)
        assert reg.get_permission_handler() is handler

    def test_set_async_handler(self):
        reg = ToolRegistry()
        handler = AsyncAlwaysAllowHandler()
        reg.set_permission_handler(handler)
        assert reg.get_permission_handler() is handler

    def test_set_handler_with_custom_fallback(self):
        reg = ToolRegistry()
        reg.set_permission_handler(
            AlwaysDenyHandler(),
            fallback=PermissionResult.ALLOW,
        )
        assert reg.permission_fallback == PermissionResult.ALLOW

    def test_remove_handler(self):
        reg = ToolRegistry()
        reg.set_permission_handler(
            AlwaysAllowHandler(),
            fallback=PermissionResult.ALLOW,
        )
        reg.remove_permission_handler()
        assert reg.get_permission_handler() is None
        assert reg.permission_fallback == PermissionResult.DENY

    def test_replace_handler(self):
        reg = ToolRegistry()
        reg.set_permission_handler(AlwaysAllowHandler())
        reg.set_permission_handler(AlwaysDenyHandler())
        assert isinstance(reg.get_permission_handler(), AlwaysDenyHandler)


# ---------------------------------------------------------------------------
# ChangeEventType new members
# ---------------------------------------------------------------------------


class TestPermissionEvents:
    def test_permission_denied_event_exists(self):
        assert ChangeEventType.PERMISSION_DENIED == "permission_denied"

    def test_permission_asked_event_exists(self):
        assert ChangeEventType.PERMISSION_ASKED == "permission_asked"
