# Concurrency Modes: Thread Mode and Process Mode

## Overview

Prior to version 0.4.5, the execution mode was determined by the number of tasks in `tool_calls`. For two or fewer tasks, the main thread executed them sequentially. For more than two tasks, a thread pool was used for parallel execution.

Version 0.4.5 introduces concurrent process mode as the default execution mode, ensuring enhanced isolation and crash prevention. Concurrent thread mode remains available as an optional backup for scenarios requiring shared memory or lower overhead.

## Design Concept

### Thread Mode

- **Purpose**: Suitable for lightweight tasks that require shared memory and minimal overhead.
- **Advantages**:
  - Faster context switching.
  - Shared memory access.
- **Limitations**:
  - Vulnerable to crashes due to shared memory corruption.

### Process Mode

- **Purpose**: Ideal for tasks requiring high isolation and safety.
- **Advantages**:
  - Independent memory space.
  - Enhanced crash resistance.
- **Limitations**:
  - Higher overhead due to inter-process communication.

## Switching Between Modes

### Configuration

The mode can be switched by modifying the ToolRegistry configuration or overridden during execution. The following steps outline the process:

By default, the `ToolRegistry` initializes with `parallel_mode` set to `"process"`. To permanently change the mode, use the `set_execution_mode` method. For single-use overrides, provide the `parallel_mode` parameter in the `execute_tool_calls` method.

#### Examples

1. **Thread Mode**:

   - Set the execution mode to `thread`.
   - Example:

     ```python
     tool_registry.set_execution_mode("thread")
     ```

2. **Process Mode (Default)**:

   - Set the execution mode to `process`.
   - Example:

     ```python
     tool_registry.set_execution_mode("process")
     ```

3. **Single-use Override**:

   - Override the mode during execution.
   - Example:

     ```python
     tool_registry.execute_tool_calls(tool_calls, parallel_mode="thread")
     ```

## Performance and Results

To evaluate the performance of concurrent execution modes, we conducted experiments using the script [`examples/test_toolregistry_concurrency.py`](https://github.com/Oaklight/ToolRegistry/blob/concurrent%2Bdill/examples/test_toolregistry_concurrency.py). The tests involved executing 100 tool calls (`N = 100`) in four scenarios: Native Function Tool, Native Class Tool, OpenAPI Tool, and MCP SSE Tool. Each tool call performed a simple mathematical addition operation. The tests measured execution time and throughput under the default `parallel_mode` set to `"process"`.

**Results**:

```text
---------- Native Func Tool ----------
Average Execution Time: 0.0415 seconds
Average Throughput: 2411.89 calls/second

---------- Native Class Tool ----------
Average Execution Time: 0.0311 seconds
Average Throughput: 3218.23 calls/second

---------- OpenAPI Tool ----------
Average Execution Time: 0.2062 seconds
Average Throughput: 485.08 calls/second

---------- MCP SSE Tool ----------
Average Execution Time: 0.7272 seconds
Average Throughput: 138.15 calls/second
```

These metrics highlight the efficiency of concurrent process mode across different tool types.

Btw, the result above is computed and written by agent with Calculator and FileOps hub tools.
