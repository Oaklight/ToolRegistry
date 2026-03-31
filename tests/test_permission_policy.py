"""Tests for PermissionRule, PermissionPolicy, built-in rules,
and execute_tool_calls integration."""

import json

from toolregistry import (
    PermissionPolicy,
    PermissionRequest,
    PermissionResult,
    PermissionRule,
    Tool,
    ToolMetadata,
    ToolRegistry,
    ToolTag,
)
from toolregistry.events import ChangeEvent, ChangeEventType
from toolregistry.permissions.builtin_rules import (
    ALLOW_READONLY,
    ASK_DESTRUCTIVE,
    ASK_FILE_SYSTEM,
    ASK_NETWORK,
    DENY_PRIVILEGED,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str = "test_tool", tags: set[ToolTag] | None = None) -> Tool:
    def _fn(x: int = 0) -> int:
        return x

    meta = ToolMetadata(tags=tags or set())
    return Tool.from_function(_fn, name=name, metadata=meta)


class _AllowHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        return PermissionResult.ALLOW


class _DenyHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        return PermissionResult.DENY


class _RecordingHandler:
    """Records requests for assertion."""

    def __init__(self, decision: PermissionResult = PermissionResult.ALLOW):
        self.requests: list[PermissionRequest] = []
        self.decision = decision

    def handle(self, request: PermissionRequest) -> PermissionResult:
        self.requests.append(request)
        return self.decision


# ---------------------------------------------------------------------------
# PermissionRule
# ---------------------------------------------------------------------------


class TestPermissionRule:
    def test_basic_match(self):
        rule = PermissionRule(
            name="test",
            match=lambda t, p: t.name == "target",
            result=PermissionResult.DENY,
        )
        tool_match = _make_tool("target")
        tool_other = _make_tool("other")
        assert rule.match(tool_match, {}) is True
        assert rule.match(tool_other, {}) is False

    def test_match_with_parameters(self):
        rule = PermissionRule(
            name="block_rm",
            match=lambda t, p: p.get("path", "").startswith("/etc"),
            result=PermissionResult.DENY,
            reason="Cannot touch /etc",
        )
        tool = _make_tool()
        assert rule.match(tool, {"path": "/etc/passwd"}) is True
        assert rule.match(tool, {"path": "/tmp/foo"}) is False

    def test_match_with_tags(self):
        rule = PermissionRule(
            name="tag_check",
            match=lambda t, p: ToolTag.DESTRUCTIVE in t.metadata.tags,
            result=PermissionResult.ASK,
        )
        tool_d = _make_tool(tags={ToolTag.DESTRUCTIVE})
        tool_r = _make_tool(tags={ToolTag.READ_ONLY})
        assert rule.match(tool_d, {}) is True
        assert rule.match(tool_r, {}) is False


# ---------------------------------------------------------------------------
# PermissionPolicy.evaluate
# ---------------------------------------------------------------------------


class TestPermissionPolicy:
    def test_first_match_wins(self):
        policy = PermissionPolicy(
            rules=[
                PermissionRule(
                    name="allow_all",
                    match=lambda t, p: True,
                    result=PermissionResult.ALLOW,
                ),
                PermissionRule(
                    name="deny_all",
                    match=lambda t, p: True,
                    result=PermissionResult.DENY,
                ),
            ],
        )
        outcome = policy.evaluate(_make_tool(), {})
        assert isinstance(outcome, PermissionRule)
        assert outcome.result == PermissionResult.ALLOW

    def test_fallback_when_no_match(self):
        policy = PermissionPolicy(
            rules=[
                PermissionRule(
                    name="never",
                    match=lambda t, p: False,
                    result=PermissionResult.DENY,
                ),
            ],
            fallback=PermissionResult.ALLOW,
        )
        outcome = policy.evaluate(_make_tool(), {})
        assert outcome == PermissionResult.ALLOW

    def test_default_fallback_is_deny(self):
        policy = PermissionPolicy(rules=[])
        outcome = policy.evaluate(_make_tool(), {})
        assert outcome == PermissionResult.DENY

    def test_empty_rules_returns_fallback(self):
        policy = PermissionPolicy(rules=[], fallback=PermissionResult.ALLOW)
        outcome = policy.evaluate(_make_tool(), {})
        assert outcome == PermissionResult.ALLOW


# ---------------------------------------------------------------------------
# Built-in rules
# ---------------------------------------------------------------------------


class TestBuiltinRules:
    def test_allow_readonly(self):
        tool_ro = _make_tool(tags={ToolTag.READ_ONLY})
        tool_other = _make_tool(tags={ToolTag.NETWORK})
        assert ALLOW_READONLY.match(tool_ro, {}) is True
        assert ALLOW_READONLY.result == PermissionResult.ALLOW
        assert ALLOW_READONLY.match(tool_other, {}) is False

    def test_ask_destructive(self):
        tool = _make_tool(tags={ToolTag.DESTRUCTIVE})
        assert ASK_DESTRUCTIVE.match(tool, {}) is True
        assert ASK_DESTRUCTIVE.result == PermissionResult.ASK

    def test_deny_privileged(self):
        tool = _make_tool(tags={ToolTag.PRIVILEGED})
        assert DENY_PRIVILEGED.match(tool, {}) is True
        assert DENY_PRIVILEGED.result == PermissionResult.DENY

    def test_ask_network(self):
        tool = _make_tool(tags={ToolTag.NETWORK})
        assert ASK_NETWORK.match(tool, {}) is True
        assert ASK_NETWORK.result == PermissionResult.ASK

    def test_ask_file_system(self):
        tool = _make_tool(tags={ToolTag.FILE_SYSTEM})
        assert ASK_FILE_SYSTEM.match(tool, {}) is True
        assert ASK_FILE_SYSTEM.result == PermissionResult.ASK


# ---------------------------------------------------------------------------
# ToolRegistry integration
# ---------------------------------------------------------------------------


def _registry_with_tool(
    tags: set[ToolTag] | None = None,
) -> tuple[ToolRegistry, str]:
    """Create a registry with a single tool, return (registry, tool_name)."""
    reg = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tool = Tool.from_function(add, metadata=ToolMetadata(tags=tags or set()))
    reg.register(tool)
    return reg, tool.name


def _make_tool_call(name: str, args: dict | None = None) -> dict:
    return {
        "id": f"call_{name}",
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args or {}),
        },
    }


class TestRegistryPolicyIntegration:
    def test_no_policy_allows_all(self):
        reg, name = _registry_with_tool()
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert str(results[f"call_{name}"]) == "3"

    def test_deny_rule_blocks_execution(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[
                    PermissionRule(
                        name="deny_destructive",
                        match=lambda t, p: ToolTag.DESTRUCTIVE in t.metadata.tags,
                        result=PermissionResult.DENY,
                        reason="Destructive tools blocked",
                    ),
                ],
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert "denied by permission policy" in results[f"call_{name}"].lower()

    def test_allow_rule_permits_execution(self):
        reg, name = _registry_with_tool(tags={ToolTag.READ_ONLY})
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[ALLOW_READONLY],
                fallback=PermissionResult.DENY,
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert str(results[f"call_{name}"]) == "3"

    def test_ask_with_handler_allow(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        handler = _RecordingHandler(PermissionResult.ALLOW)
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[ASK_DESTRUCTIVE],
                handler=handler,
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert str(results[f"call_{name}"]) == "3"
        assert len(handler.requests) == 1
        assert handler.requests[0].tool_name == name

    def test_ask_with_handler_deny(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        handler = _RecordingHandler(PermissionResult.DENY)
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[ASK_DESTRUCTIVE],
                handler=handler,
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert "denied" in results[f"call_{name}"].lower()

    def test_ask_no_handler_uses_fallback(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[ASK_DESTRUCTIVE],
                fallback=PermissionResult.DENY,
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert "denied" in results[f"call_{name}"].lower()

    def test_ask_uses_registry_handler_when_policy_has_none(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        handler = _RecordingHandler(PermissionResult.ALLOW)
        reg.set_permission_handler(handler)
        reg.set_permission_policy(PermissionPolicy(rules=[ASK_DESTRUCTIVE]))
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert str(results[f"call_{name}"]) == "3"
        assert len(handler.requests) == 1

    def test_policy_handler_takes_precedence(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        registry_handler = _RecordingHandler(PermissionResult.DENY)
        policy_handler = _RecordingHandler(PermissionResult.ALLOW)
        reg.set_permission_handler(registry_handler)
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[ASK_DESTRUCTIVE],
                handler=policy_handler,
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        # Policy handler should be used, not registry handler
        assert str(results[f"call_{name}"]) == "3"
        assert len(policy_handler.requests) == 1
        assert len(registry_handler.requests) == 0

    def test_remove_policy(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[
                    PermissionRule(
                        name="deny_all",
                        match=lambda t, p: True,
                        result=PermissionResult.DENY,
                    ),
                ],
            )
        )
        reg.remove_permission_policy()
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert str(results[f"call_{name}"]) == "3"

    def test_fallback_no_match_no_handler(self):
        reg, name = _registry_with_tool()
        reg.set_permission_policy(
            PermissionPolicy(
                rules=[
                    PermissionRule(
                        name="never_matches",
                        match=lambda t, p: False,
                        result=PermissionResult.ALLOW,
                    ),
                ],
                fallback=PermissionResult.DENY,
            )
        )
        tc = _make_tool_call(name, {"a": 1, "b": 2})
        results = reg.execute_tool_calls([tc])
        assert "denied" in results[f"call_{name}"].lower()


# ---------------------------------------------------------------------------
# Events emitted during permission evaluation
# ---------------------------------------------------------------------------


class TestPermissionEvents:
    def test_deny_emits_permission_denied(self):
        reg, name = _registry_with_tool(tags={ToolTag.PRIVILEGED})
        events: list[ChangeEvent] = []
        reg.on_change(events.append)
        reg.set_permission_policy(PermissionPolicy(rules=[DENY_PRIVILEGED]))

        tc = _make_tool_call(name, {"a": 1, "b": 2})
        reg.execute_tool_calls([tc])

        denied = [
            e for e in events if e.event_type == ChangeEventType.PERMISSION_DENIED
        ]
        assert len(denied) == 1
        assert denied[0].tool_name == name

    def test_ask_emits_permission_asked(self):
        reg, name = _registry_with_tool(tags={ToolTag.DESTRUCTIVE})
        events: list[ChangeEvent] = []
        reg.on_change(events.append)
        handler = _RecordingHandler(PermissionResult.ALLOW)
        reg.set_permission_policy(
            PermissionPolicy(rules=[ASK_DESTRUCTIVE], handler=handler)
        )

        tc = _make_tool_call(name, {"a": 1, "b": 2})
        reg.execute_tool_calls([tc])

        asked = [e for e in events if e.event_type == ChangeEventType.PERMISSION_ASKED]
        assert len(asked) == 1
        assert asked[0].tool_name == name
