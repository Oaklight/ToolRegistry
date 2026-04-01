"""Demo: Execution Logging & Admin Panel

This example demonstrates:
1. Registering tools with ToolRegistry (functions + class methods)
2. Enabling execution logging to track tool calls
3. Launching the admin panel (web UI + REST API)
4. Executing tool calls and inspecting logs/stats
5. Class-level and method-level enable/disable

Usage:
    python examples/admin_demo.py
"""

import time

from toolregistry import ToolRegistry


# ── 1. Create registry and register some tools ──────────────────────────

registry = ToolRegistry()
registry.set_default_execution_mode("thread")  # Use threads for faster execution


@registry.register
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@registry.register
def divide(a: float, b: float) -> float:
    """Divide a by b."""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b


@registry.register
def greet(name: str = "World") -> str:
    """Greet someone."""
    return f"Hello, {name}!"


# Register a class with methods (namespace = "StringUtils")
class StringUtils:
    """String utility tools."""

    def reverse(self, text: str) -> str:
        """Reverse a string."""
        return text[::-1]

    def char_count(self, text: str) -> int:
        """Count characters in a string."""
        return len(text)


registry.register_from_class(StringUtils, namespace="StringUtils")


# ── 2. Enable execution logging ─────────────────────────────────────────

log = registry.enable_logging(max_entries=500)
print("[+] Execution logging enabled (max 500 entries)\n")

# ── 3. Launch admin panel ────────────────────────────────────────────────

info = registry.enable_admin(port=8081)
print(f"[+] Admin panel running at: {info.url}")
if info.token:
    print(f"    Auth token: {info.token}")
print()

# ── 4. Execute some tool calls ───────────────────────────────────────────

# Simulate tool calls in the format used by LLM function calling
tool_calls = [
    {"id": "call_1", "function": {"name": "add", "arguments": '{"a": 3, "b": 5}'}},
    {
        "id": "call_2",
        "function": {"name": "string_utils-reverse", "arguments": '{"text": "hello"}'},
    },
    {
        "id": "call_3",
        "function": {
            "name": "string_utils-char_count",
            "arguments": '{"text": "hello world"}',
        },
    },
    {"id": "call_4", "function": {"name": "greet", "arguments": '{"name": "Alice"}'}},
    {"id": "call_5", "function": {"name": "divide", "arguments": '{"a": 10, "b": 0}'}},
]

print("[*] Executing tool calls...")
results = registry.execute_tool_calls(tool_calls)
for call_id, result in results.items():
    print(f"    {call_id}: {result}")
print()

# ── 4b. Disable a single method and call it ──────────────────────────────

registry.disable("string_utils-reverse", reason="maintenance")
tool_calls_2 = [
    {
        "id": "call_6",
        "function": {"name": "string_utils-reverse", "arguments": '{"text": "test"}'},
    },
    {
        "id": "call_7",
        "function": {
            "name": "string_utils-char_count",
            "arguments": '{"text": "test"}',
        },
    },
]

print("[*] Executing with 'string_utils-reverse' disabled (method-level)...")
results2 = registry.execute_tool_calls(tool_calls_2)
for call_id, result in results2.items():
    print(f"    {call_id}: {result}")
print()

# Re-enable the method, then disable at namespace level
registry.enable("string_utils-reverse")
registry.disable("string_utils", reason="namespace offline")
tool_calls_3 = [
    {
        "id": "call_8",
        "function": {"name": "string_utils-reverse", "arguments": '{"text": "test"}'},
    },
    {
        "id": "call_9",
        "function": {
            "name": "string_utils-char_count",
            "arguments": '{"text": "test"}',
        },
    },
    {"id": "call_10", "function": {"name": "add", "arguments": '{"a": 10, "b": 20}'}},
]

print("[*] Executing with 'string_utils' namespace disabled (class-level)...")
results3 = registry.execute_tool_calls(tool_calls_3)
for call_id, result in results3.items():
    print(f"    {call_id}: {result}")
print()

# Re-enable namespace for admin panel demo
registry.enable("string_utils")

# ── 5. Inspect execution logs ────────────────────────────────────────────

print("[*] Execution log entries:")
for entry in log.get_entries():
    status_icon = {"success": "+", "error": "!", "disabled": "-"}[entry.status.value]
    print(
        f"    [{status_icon}] {entry.tool_name}: {entry.status.value} ({entry.duration_ms:.1f}ms)"
    )
print()

# ── 6. Show stats ───────────────────────────────────────────────────────

stats = log.get_stats()
print("[*] Execution stats:")
print(f"    Total executions: {stats['total_entries']}")
print(f"    By status: {stats['by_status']}")
print(f"    By tool: {stats['by_tool']}")
print(f"    Avg duration: {stats['avg_duration_ms']:.2f}ms")
print()

# ── 7. Keep alive for admin panel browsing ──────────────────────────────

print(f"[*] Open {info.url} in your browser to explore the admin panel.")
print("    Press Ctrl+C to stop.\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[*] Shutting down...")
    registry.disable_admin()
    registry.disable_logging()
    print("[+] Done.")
