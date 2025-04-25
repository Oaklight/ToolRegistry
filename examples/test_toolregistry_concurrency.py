"""Test script for ToolRegistry concurrent tool execution with Calculator."""

import json
import os
import random
import string
import time
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple

from toolregistry import ToolRegistry
from toolregistry.utils import (
    ChatCompletionMessageToolCall,
    Function,
)


def analyze_results(
    results: Dict[str, Any], N: int, elapsed: float
) -> Tuple[float, float]:
    """Analyze tool execution results and calculate metrics.

    Args:
        results: Dictionary of tool call results
        N: Expected number of results
        elapsed: Execution time in seconds

    Returns:
        Tuple of (success_rate, throughput)
    """
    error_count = 0
    for call_id, result_val in results.items():
        if isinstance(result_val, str) and "Error" in result_val:
            error_count += 1
            print(f"Call {call_id} error: {result_val}")

    success_count = N - error_count
    success_rate = success_count / N * 100
    throughput = N / elapsed if elapsed > 0 else 0

    print(f"Got {len(results)} results out of {N} calls.")
    print(f"Success rate: {success_rate:.2f}% ({success_count}/{N})")
    if error_count > 0:
        print(f"Warning: {error_count} tool calls failed")
    if error_count / N > 0.01:  # Allow up to 1% failure rate
        print("Error: Failure rate too high")

    return success_rate, throughput


# [ChatCompletionMessageToolCall(id='call_egkg4evbb19d8012bex83v8a', function=Function(arguments='{"a":15,"b":3}', name='subtract'), type='function', index=0)]


def local_add(a: float, b: float) -> float:
    return a + b


def local_subtract(a: float, b: float) -> float:
    return a - b


def local_multiply(a: float, b: float) -> float:
    return a * b


def local_divide(a: float, b: float) -> float:
    return a / b


EXEC_MODE = os.getenv("EXEC_MODE", "process")
FUNC = os.getenv("FUNC", None)
N = os.getenv("N", 100)


def generate_tool_calls(
    n: int, available_names: List[str], callable_name: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Generate n simulated tool calls with random operations."""

    # Define candidate subnames
    candidate_subnames = (
        [callable_name] if callable_name else ["add", "subtract", "multiply", "divide"]
    )

    # Filter available names based on candidate_subnames
    names = [
        name
        for name in available_names
        if any(subname in name for subname in candidate_subnames)
    ]

    if not names:
        raise ValueError(
            f"No available names found matching the criteria: {candidate_subnames}"
        )

    # Select final names based on callable_name presence
    final_names = [callable_name] * n if callable_name else random.choices(names, k=n)
    # Generate tool call data
    return [
        ChatCompletionMessageToolCall(
            id="id_" + "".join(random.choices(string.hexdigits, k=4)),
            function=Function(
                name=final_names[i],
                arguments=json.dumps(
                    {
                        "a": random.randint(1, 100),
                        "b": random.randint(1, 100),
                    }
                ),
            ),
            type="function",
        )
        for i in range(n)
    ]


def main():

    # ========= native func tools =========
    print("-" * 10 + f" Native Func Tool " + "-" * 10)

    registry = ToolRegistry()
    registry.register(local_add)
    registry.register(local_subtract)
    registry.register(local_multiply)
    registry.register(local_divide)
    print(registry.get_available_tools())
    if FUNC:
        target_func_name = [
            name for name in registry.get_available_tools() if FUNC in name
        ][0]
    else:
        target_func_name = None
    tool_calls = generate_tool_calls(
        N, registry.get_available_tools(), target_func_name
    )

    start_time = time.time()
    results = registry.execute_tool_calls(tool_calls, execution_mode=EXEC_MODE)
    elapsed = time.time() - start_time

    success_rate, throughput = analyze_results(results, N, elapsed)
    print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
    print(f"Throughput: {throughput:.2f} calls/second")

    # ========= native (hub) class tools =========
    print("-" * 10 + f" Native Class Tool " + "-" * 10)
    from toolregistry.hub import Calculator

    registry = ToolRegistry()
    registry.register_from_class(Calculator, with_namespace=True)
    # print(registry.get_available_tools())
    if FUNC:
        target_func_name = [
            name for name in registry.get_available_tools() if FUNC in name
        ][0]
    else:
        target_func_name = None
    tool_calls = generate_tool_calls(
        N, registry.get_available_tools(), target_func_name
    )

    start_time = time.time()
    results = registry.execute_tool_calls(tool_calls, execution_mode=EXEC_MODE)
    elapsed = time.time() - start_time

    success_rate, throughput = analyze_results(results, N, elapsed)
    print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
    print(f"Throughput: {throughput:.2f} calls/second")

    # ========= openapi tools =========
    print("-" * 10 + f" OpenAPI Tool " + "-" * 10)
    registry = ToolRegistry()

    OPENAPI_PORT = os.getenv("OPENAPI_PORT", 8000)
    registry.register_from_openapi(
        f"http://localhost:{OPENAPI_PORT}", with_namespace=True
    )
    # print(registry.get_available_tools())
    if FUNC:
        target_func_name = [
            name for name in registry.get_available_tools() if FUNC in name
        ][0]
    else:
        target_func_name = None
    tool_calls = generate_tool_calls(
        N, registry.get_available_tools(), target_func_name
    )

    start_time = time.time()
    results = registry.execute_tool_calls(tool_calls, execution_mode=EXEC_MODE)
    elapsed = time.time() - start_time

    success_rate, throughput = analyze_results(results, N, elapsed)
    print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
    print(f"Throughput: {throughput:.2f} calls/second")

    # ========= mcp tools =========
    print("-" * 10 + f" MCP SSE Tool " + "-" * 10)
    registry = ToolRegistry()

    MCP_PORT = os.getenv("MCP_PORT", 8001)
    registry.register_from_mcp(
        f"http://localhost:{MCP_PORT}/mcp/sse", with_namespace=True
    )
    # print(registry.get_available_tools())
    if FUNC:
        target_func_name = [
            name for name in registry.get_available_tools() if FUNC in name
        ][0]
    else:
        target_func_name = None
    tool_calls = generate_tool_calls(
        N, registry.get_available_tools(), target_func_name
    )

    start_time = time.time()
    results = registry.execute_tool_calls(tool_calls, execution_mode=EXEC_MODE)
    elapsed = time.time() - start_time

    success_rate, throughput = analyze_results(results, N, elapsed)
    print(f"Executed {N} tool calls in {elapsed:.4f} seconds")
    print(f"Throughput: {throughput:.2f} calls/second")


if __name__ == "__main__":
    main()
