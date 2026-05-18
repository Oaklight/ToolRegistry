"""Tests for the post-registration hook interface.

Covers:
- Hook is invoked with the correct arguments after registration.
- Returning a non-empty string auto-disables the tool with that reason.
- Returning None leaves the tool enabled.
- Multiple hooks are called in registration order.
- An exception inside a hook does not affect the registration flow or
  subsequent hooks.
"""

from __future__ import annotations


from toolregistry import Tool, ToolRegistry


# ============== Helper functions ==============


def _make_tool_func(name: str = "my_tool"):
    """Create a trivial callable suitable for registration."""

    def tool_func():
        """A simple test tool."""
        return "ok"

    tool_func.__name__ = name
    return tool_func


# ============== Hook invocation tests ==============


class TestHookInvocation:
    """Verify that the hook is called with the expected arguments."""

    def test_hook_called_after_register(self):
        """Hook receives (tool_name, tool, registry) after register()."""
        registry = ToolRegistry()
        calls: list[tuple] = []

        def hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            calls.append((name, tool, reg))
            return None

        registry.add_post_register_hook(hook)
        registry.register(_make_tool_func("alpha"))

        assert len(calls) == 1
        name, tool, reg = calls[0]
        assert name == "alpha"
        assert isinstance(tool, Tool)
        assert tool.name == "alpha"
        assert reg is registry

    def test_hook_called_for_each_tool_in_register_from_class(self):
        """Hook is called once per tool when using register_from_class()."""
        registry = ToolRegistry()
        seen: list[str] = []

        def hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            seen.append(name)
            return None

        registry.add_post_register_hook(hook)

        class MyClass:
            @staticmethod
            def tool_a() -> str:
                """Tool A."""
                return "a"

            @staticmethod
            def tool_b() -> str:
                """Tool B."""
                return "b"

        registry.register_from_class(MyClass)

        assert "tool_a" in seen
        assert "tool_b" in seen
        assert len(seen) == 2

    def test_hook_called_with_tool_instance_registration(self):
        """Hook works when a Tool instance is passed to register()."""
        registry = ToolRegistry()
        calls: list[str] = []

        def hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            calls.append(name)
            return None

        registry.add_post_register_hook(hook)

        tool = Tool.from_function(_make_tool_func("beta"))
        registry.register(tool)

        assert calls == ["beta"]


# ============== Auto-disable tests ==============


class TestAutoDisable:
    """Verify auto-disable behaviour based on hook return value."""

    def test_return_string_disables_tool(self):
        """Returning a non-empty string from the hook disables the tool."""
        registry = ToolRegistry()

        def blocking_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            return "blocked by policy"

        registry.add_post_register_hook(blocking_hook)
        registry.register(_make_tool_func("restricted"))

        assert not registry.is_enabled("restricted")
        assert registry.get_disable_reason("restricted") == "blocked by policy"

    def test_return_none_keeps_tool_enabled(self):
        """Returning None from the hook leaves the tool enabled."""
        registry = ToolRegistry()

        def permissive_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            return None

        registry.add_post_register_hook(permissive_hook)
        registry.register(_make_tool_func("allowed"))

        assert registry.is_enabled("allowed")

    def test_return_empty_string_keeps_tool_enabled(self):
        """Returning an empty string (falsy) does NOT disable the tool."""
        registry = ToolRegistry()

        def falsy_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            return ""  # type: ignore[return-value]

        registry.add_post_register_hook(falsy_hook)
        registry.register(_make_tool_func("keep_me"))

        assert registry.is_enabled("keep_me")

    def test_selective_disable_based_on_name(self):
        """Hook can selectively disable only certain tools."""
        registry = ToolRegistry()

        def selective_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            if name.startswith("bad_"):
                return "name prefix is disallowed"
            return None

        registry.add_post_register_hook(selective_hook)
        registry.register(_make_tool_func("bad_tool"))
        registry.register(_make_tool_func("good_tool"))

        assert not registry.is_enabled("bad_tool")
        assert registry.is_enabled("good_tool")


# ============== Multiple hooks tests ==============


class TestMultipleHooks:
    """Verify that multiple hooks are invoked in registration order."""

    def test_multiple_hooks_called_in_order(self):
        """Hooks are invoked in the order they were registered."""
        registry = ToolRegistry()
        order: list[int] = []

        registry.add_post_register_hook(lambda n, t, r: (order.append(1), None)[1])
        registry.add_post_register_hook(lambda n, t, r: (order.append(2), None)[1])
        registry.add_post_register_hook(lambda n, t, r: (order.append(3), None)[1])

        registry.register(_make_tool_func("ordered"))

        assert order == [1, 2, 3]

    def test_all_hooks_run_even_if_first_disables(self):
        """All hooks run even when an earlier hook auto-disables the tool."""
        registry = ToolRegistry()
        calls: list[int] = []

        def hook1(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            calls.append(1)
            return "disabled by hook1"

        def hook2(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            calls.append(2)
            return None

        registry.add_post_register_hook(hook1)
        registry.add_post_register_hook(hook2)
        registry.register(_make_tool_func("multi"))

        assert calls == [1, 2]
        # hook1 wins; tool is disabled
        assert not registry.is_enabled("multi")

    def test_last_disable_reason_wins(self):
        """If multiple hooks disable a tool, the last reason is recorded."""
        registry = ToolRegistry()

        def hook_a(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            return "reason A"

        def hook_b(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            return "reason B"

        registry.add_post_register_hook(hook_a)
        registry.add_post_register_hook(hook_b)
        registry.register(_make_tool_func("contested"))

        # disable() is called twice; second call overwrites the first
        assert not registry.is_enabled("contested")
        assert registry.get_disable_reason("contested") == "reason B"

    def test_same_hook_registered_twice(self):
        """The same hook can be registered multiple times and runs twice."""
        registry = ToolRegistry()
        calls: list[str] = []

        def hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            calls.append(name)
            return None

        registry.add_post_register_hook(hook)
        registry.add_post_register_hook(hook)
        registry.register(_make_tool_func("double"))

        assert calls == ["double", "double"]


# ============== Exception isolation tests ==============


class TestHookExceptionIsolation:
    """Verify that hook exceptions never propagate and don't skip later hooks."""

    def test_exception_does_not_propagate(self):
        """An exception inside a hook must not propagate to the caller."""
        registry = ToolRegistry()

        def bad_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            raise RuntimeError("hook failure")

        registry.add_post_register_hook(bad_hook)

        # Must not raise
        registry.register(_make_tool_func("safe"))
        assert "safe" in registry

    def test_exception_does_not_skip_subsequent_hooks(self):
        """A raising hook must not prevent later hooks from running."""
        registry = ToolRegistry()
        later_called: list[bool] = []

        def bad_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            raise ValueError("first hook blows up")

        def good_hook(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            later_called.append(True)
            return None

        registry.add_post_register_hook(bad_hook)
        registry.add_post_register_hook(good_hook)
        registry.register(_make_tool_func("resilient"))

        assert later_called == [True]

    def test_tool_is_registered_despite_hook_exception(self):
        """Tool registration succeeds even when a hook raises."""
        registry = ToolRegistry()

        def always_raises(name: str, tool: Tool, reg: ToolRegistry) -> str | None:
            raise TypeError("unexpected")

        registry.add_post_register_hook(always_raises)
        registry.register(_make_tool_func("survives"))

        assert "survives" in registry
        # No disable was triggered, so tool is still enabled
        assert registry.is_enabled("survives")


# ============== Integration tests ==============


class TestIntegration:
    """Integration tests combining hooks with other registry features."""

    def test_hook_registered_before_tools(self):
        """Hook registered before any tools fires for all subsequent tools."""
        registry = ToolRegistry()
        seen: list[str] = []

        registry.add_post_register_hook(lambda n, t, r: (seen.append(n), None)[1])

        for i in range(3):
            registry.register(_make_tool_func(f"tool_{i}"))

        assert seen == ["tool_0", "tool_1", "tool_2"]

    def test_hook_does_not_interfere_with_on_change(self):
        """PostRegisterHook and on_change callbacks co-exist independently."""
        from toolregistry import ChangeEvent, ChangeEventType

        registry = ToolRegistry()
        hook_calls: list[str] = []
        change_events: list[ChangeEvent] = []

        registry.add_post_register_hook(lambda n, t, r: (hook_calls.append(n), None)[1])
        registry.on_change(change_events.append)

        registry.register(_make_tool_func("coexist"))

        assert hook_calls == ["coexist"]
        assert len(change_events) == 1
        assert change_events[0].event_type == ChangeEventType.REGISTER
        assert change_events[0].tool_name == "coexist"

    def test_post_register_hook_type_alias_importable(self):
        """PostRegisterHook can be imported from the top-level package."""
        from toolregistry import PostRegisterHook as PRH  # noqa: N811

        assert PRH is not None
