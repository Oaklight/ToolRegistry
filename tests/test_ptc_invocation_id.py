"""Tests that PtcTool generates and groups ``tr_ptc_`` invocation IDs.

These exercise the PTC → ``registry._invoke_raw`` path: PTC-authored code
calls tools which are logged under a shared ``tr_ptc_`` invocation ID, and
each ``execute`` gets a fresh ID.
"""

import pytest

from toolregistry import ToolRegistry
from toolregistry.runtimes import PTC_TOOL_NAME


@pytest.fixture
def registry():
    reg = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    reg.register(add)
    reg.enable_logging()
    return reg


class TestPtcInvocationId:
    def test_ptc_generates_invocation_id(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)
        tool.run({"code": "print(add(a=1, b=2))"})

        assert registry.ptc.last_invocation_id is not None
        assert registry.ptc.last_invocation_id.startswith("tr_ptc_")

    def test_ptc_tool_calls_share_id(self, registry):
        def mul(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        registry.register(mul)
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)

        tool.run({"code": "s = add(a=1, b=2)\np = mul(a=s, b=3)\nprint(p)"})

        inv_id = registry.ptc.last_invocation_id
        entries = registry.get_execution_log().get_entries(invocation_id=inv_id)
        assert len(entries) == 2
        tool_names = {e.tool_name for e in entries}
        assert tool_names == {"add", "mul"}

    def test_separate_executions_have_different_ids(self, registry):
        registry.ptc.enable()
        tool = registry.get_tool(PTC_TOOL_NAME)

        tool.run({"code": "print(add(a=1, b=2))"})
        id1 = registry.ptc.last_invocation_id

        tool.run({"code": "print(add(a=3, b=4))"})
        id2 = registry.ptc.last_invocation_id

        assert id1 != id2
