"""Test script for ToolRegistry concurrent tool execution with Calculator."""

import json
import os
import string
import time
from pprint import pprint
from typing import Any, Dict, List

from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)

from toolregistry import ToolRegistry

# [ChatCompletionMessageToolCall(id='call_egkg4evbb19d8012bex83v8a', function=Function(arguments='{"a":15,"b":3}', name='subtract'), type='function', index=0)]


def local_add(a: float, b: float) -> float:
    return a + b


PARALLEL_MODE = os.getenv("PARALLEL_MODE", "process")

def generate_tool_calls(n: int, callable_name: str = "add") -> List[Dict[str, Any]]:
    """Generate n simulated tool calls with random operations."""
    import random

    return [
        ChatCompletionMessageToolCall(
            id="id_" + "".join(random.sample(string.hexdigits, 4)),
            function=Function(
                arguments=json.dumps(
                    {
                        "a": random.randint(1, 100),
                        "b": random.randint(1, 100),
                    }
                ),
                name=callable_name,
            ),
            type="function",
        )
        for _ in range(n)
    ]

N = 100

# ========= native func tools =========
print("-" * 10 + f" Native Func Tool " + "-" * 10)

registry = ToolRegistry()
registry.register(local_add)
# print(registry.get_available_tools())
target_func_name = [name for name in registry.get_available_tools() if "add" in name]
print(target_func_name)
tool_calls = generate_tool_calls(N, target_func_name[0])

start_time = time.time()
results = registry.execute_tool_calls(tool_calls, parallel_mode=PARALLEL_MODE)
elapsed = time.time() - start_time

assert len(results) == N

# pprint(results)

print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
print(f"Throughput: {N/elapsed:.2f} calls/second")

# ========= native (hub) class tools =========
print("-" * 10 + f" Native Class Tool " + "-" * 10)
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_from_class(Calculator, with_namespace=True)
# print(registry.get_available_tools())
target_func_name = [name for name in registry.get_available_tools() if "add" in name]
print(target_func_name)
tool_calls = generate_tool_calls(N, target_func_name[0])

start_time = time.time()
results = registry.execute_tool_calls(tool_calls, parallel_mode=PARALLEL_MODE)
elapsed = time.time() - start_time

assert len(results) == N

# pprint(results)

print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
print(f"Throughput: {N/elapsed:.2f} calls/second")

# ========= openapi tools =========
print("-" * 10 + f" OpenAPI Tool " + "-" * 10)
registry = ToolRegistry()

OPENAPI_PORT = os.getenv("OPENAPI_PORT", 8000)
registry.register_from_openapi(f"http://localhost:{OPENAPI_PORT}", with_namespace=True)
# print(registry.get_available_tools())
target_func_name = [name for name in registry.get_available_tools() if "add" in name]
print(target_func_name)
tool_calls = generate_tool_calls(N, target_func_name[0])

start_time = time.time()
results = registry.execute_tool_calls(tool_calls, parallel_mode=PARALLEL_MODE)
elapsed = time.time() - start_time

assert len(results) == N

# pprint(results)

print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
print(f"Throughput: {N/elapsed:.2f} calls/second")

# ========= mcp tools =========
print("-" * 10 + f" MCP SSE Tool " + "-" * 10)
registry = ToolRegistry()

MCP_PORT = os.getenv("MCP_PORT", 8001)
registry.register_from_mcp(f"http://localhost:{MCP_PORT}/mcp/sse", with_namespace=True)
# print(registry.get_available_tools())
target_func_name = [name for name in registry.get_available_tools() if "add" in name]
print(target_func_name)
tool_calls = generate_tool_calls(N, target_func_name[0])

start_time = time.time()
results = registry.execute_tool_calls(tool_calls, parallel_mode=PARALLEL_MODE)
elapsed = time.time() - start_time

assert len(results) == N

# pprint(results)

print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
print(f"Throughput: {N/elapsed:.2f} calls/second")
