"""Tool discovery modes, and the policy contract of the ``call_deferred`` proxy.

Discovery has three modes: ``auto`` follows the deferred set, while ``on`` and
``off`` are explicit choices that later registrations do not override.  The
policy tests pin the property the proxy has to keep: ``call_deferred`` routes
the call through the registry's normal access check, so the *target's* rules —
including parameter-dependent ones — decide, not the proxy's own.
"""

from __future__ import annotations

import pytest

from toolregistry import (
    PermissionPolicy,
    PermissionResult,
    PermissionRule,
    Tool,
    ToolMetadata,
    ToolRegistry,
)
from toolregistry.events import ChangeEventType
from toolregistry.llm.discovery import TOOL_CALL_DEFERRED_NAME, TOOL_DISCOVERY_NAME


def _hidden() -> Tool:
    def hidden(x: int = 1) -> int:
        """A deferred tool."""
        return x

    return Tool.from_function(hidden, name="hidden", metadata=ToolMetadata(defer=True))


def _hidden_two() -> Tool:
    def hidden_two(x: int = 1) -> int:
        """Another deferred tool."""
        return x

    return Tool.from_function(
        hidden_two, name="hidden_two", metadata=ToolMetadata(defer=True)
    )


def _visible() -> Tool:
    def visible(x: int = 1) -> int:
        """A tool that is always in the schema."""
        return x

    return Tool.from_function(visible, name="visible")


class TestAutoMode:
    """The default mode follows the deferred set in both directions."""

    def test_auto_is_the_default(self) -> None:
        registry = ToolRegistry()
        assert registry.tool_discovery_mode == "auto"
        assert registry.tool_discovery_enabled is False

    def test_plain_tool_does_not_enable_discovery(self) -> None:
        registry = ToolRegistry()
        registry.register(_visible())
        assert registry.tool_discovery_enabled is False

    def test_deferred_tool_turns_discovery_on(self) -> None:
        registry = ToolRegistry()
        registry.register(_hidden())

        assert registry.tool_discovery_enabled is True
        names = registry.list_tools()
        assert TOOL_DISCOVERY_NAME in names
        assert TOOL_CALL_DEFERRED_NAME in names

    def test_undeferring_the_last_tool_turns_discovery_off(self) -> None:
        registry = ToolRegistry()
        registry.register(_hidden())
        registry.update_tool_metadata("hidden", defer=False)

        assert registry.tool_discovery_enabled is False
        assert TOOL_DISCOVERY_NAME not in registry._tools

    def test_disabling_the_last_deferred_tool_turns_discovery_off(self) -> None:
        registry = ToolRegistry()
        registry.register(_hidden())
        registry.disable("hidden")

        assert registry.tool_discovery_enabled is False

    def test_another_deferred_tool_keeps_discovery_on(self) -> None:
        registry = ToolRegistry()
        registry.register(_hidden())
        registry.register(_hidden_two())

        registry.update_tool_metadata("hidden", defer=False)

        assert registry.tool_discovery_enabled is True


class TestExplicitModes:
    """``on`` and ``off`` win over the deferred set till they are changed."""

    def test_enable_pins_on(self) -> None:
        registry = ToolRegistry()
        registry.enable_tool_discovery()

        assert registry.tool_discovery_mode == "on"
        registry.register(_visible())
        assert registry.tool_discovery_enabled is True

    def test_disable_pins_off(self) -> None:
        registry = ToolRegistry()
        registry.set_tool_discovery_mode("off")
        registry.register(_hidden())

        assert registry.tool_discovery_mode == "off"
        assert registry.tool_discovery_enabled is False
        assert TOOL_DISCOVERY_NAME not in registry._tools

    def test_auto_reconciles_immediately(self) -> None:
        registry = ToolRegistry()
        registry.set_tool_discovery_mode("off")
        registry.register(_hidden())
        assert registry.tool_discovery_enabled is False

        registry.set_tool_discovery_mode("auto")

        assert registry.tool_discovery_enabled is True

    def test_invalid_mode_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            ToolRegistry().set_tool_discovery_mode("sometimes")  # type: ignore[arg-type]

    def test_disable_emits_unregister_for_both_tools(self) -> None:
        """Transports refresh on UNREGISTER; a silent removal leaves them stale."""
        registry = ToolRegistry()
        registry.enable_tool_discovery()
        seen: list[tuple[ChangeEventType, str | None]] = []
        registry.on_change(
            lambda event: seen.append((event.event_type, event.tool_name))
        )

        registry.set_tool_discovery_mode("off")

        assert (ChangeEventType.UNREGISTER, TOOL_DISCOVERY_NAME) in seen
        assert (ChangeEventType.UNREGISTER, TOOL_CALL_DEFERRED_NAME) in seen


class TestCallDeferredPolicy:
    """The proxy must not be a way around the target's permission policy."""

    @staticmethod
    def _policy(rules: list[PermissionRule]) -> PermissionPolicy:
        return PermissionPolicy(rules=rules, fallback=PermissionResult.ALLOW)

    def test_denied_target_is_denied_through_the_proxy(self) -> None:
        registry = ToolRegistry()
        registry.register(_hidden())
        registry.set_permission_policy(
            self._policy(
                [
                    PermissionRule(
                        name="deny-hidden",
                        match=lambda tool, params: tool.name == "hidden",
                        result=PermissionResult.DENY,
                    )
                ]
            )
        )

        with pytest.raises(PermissionError):
            registry._invoke_raw(
                TOOL_CALL_DEFERRED_NAME, {"_target_tool": "hidden", "x": 2}
            )

    def test_target_parameters_reach_the_policy(self) -> None:
        """A rule that depends on arguments sees the target's arguments."""
        registry = ToolRegistry()
        registry.register(_hidden())
        registry.set_permission_policy(
            self._policy(
                [
                    PermissionRule(
                        name="deny-large",
                        match=lambda tool, params: (
                            tool.name == "hidden" and params.get("x", 0) > 5
                        ),
                        result=PermissionResult.DENY,
                    )
                ]
            )
        )

        assert (
            registry._invoke_raw(
                TOOL_CALL_DEFERRED_NAME, {"_target_tool": "hidden", "x": 1}
            )
            == 1
        )
        with pytest.raises(PermissionError):
            registry._invoke_raw(
                TOOL_CALL_DEFERRED_NAME, {"_target_tool": "hidden", "x": 9}
            )

    def test_allowed_target_runs_through_the_proxy(self) -> None:
        registry = ToolRegistry()
        registry.register(_hidden())

        assert (
            registry._invoke_raw(
                TOOL_CALL_DEFERRED_NAME, {"_target_tool": "hidden", "x": 3}
            )
            == 3
        )
