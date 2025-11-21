# Concurrency Modes: Thread Mode and Process Mode

???+ note "Changelog"
    New in version: 0.4.5

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

To evaluate the performance of concurrent execution modes, we conducted experiments using the script [`examples/test_toolregistry_concurrency.py`](https://github.com/Oaklight/ToolRegistry/blob/concurrent%2Bdill/examples/test_toolregistry_concurrency.py). The tests involved executing 100 tool calls (`N = 100`) in four scenarios: Native Function Tool, Native Class Tool, OpenAPI Tool, and MCP SSE Tool. Each tool call performed a simple random mathematical operation (`add`, `subtract`, `multiply` and `divide`). The tests measured execution time and throughput under both `"process"` and `thread` mode.

### Performance Comparison of Concurrency Modes

#### Performance Logs

```bash
$ EXEC_MODE=thread python examples/test_toolregistry_concurrency.py
---------- Native Func Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.021 seconds
Average throughput: 4772.17 calls/second
---------- Native Class Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.0083 seconds
Average throughput: 12125.03 calls/second
---------- OpenAPI Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 3.5234 seconds
Average throughput: 28.40 calls/second
---------- MCP SSE Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 3.6547 seconds
Average throughput: 27.39 calls/second

$ EXEC_MODE=process python examples/test_toolregistry_concurrency.py
---------- Native Func Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.0425 seconds
Average throughput: 2357.26 calls/second
---------- Native Class Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.0332 seconds
Average throughput: 3010.66 calls/second
---------- OpenAPI Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.2216 seconds
Average throughput: 451.28 calls/second
---------- MCP SSE Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.7551 seconds
Average throughput: 132.44 calls/second
```

Note: this computation is done by `cicada-agent` with a `ToolRegistry` of `Calculator` and `FileOps` as a demo.

#### Analysis

1. **MCP Integration Implementation**

- MCP tool synchronous calls create and close event loops on each call, causing overhead.
- Asynchronous calls use SSE long connections and event loops, with network I/O and event loop scheduling overhead.
- Thread mode shares process resources among threads, causing resource contention in event loops and network connections, leading to performance bottlenecks (27.39 calls/second).
- Process mode uses independent event loops and network connections per process, reducing contention and improving throughput (132.44 calls/second).

2. **OpenAPI Integration Implementation**

- OpenAPI tool synchronous calls use httpx synchronous client; asynchronous calls use httpx asynchronous client.
- Thread mode with many threads issuing network requests causes thread switching and network I/O contention, reducing performance (28.40 calls/second).
- Process mode uses independent processes, avoiding GIL and thread context switching overhead, improving network I/O scheduling (451.28 calls/second).

3. **Native Local Tool Calls**

- Native function and class tool calls are mainly CPU and memory operations; thread mode releases GIL and has low thread switching overhead, resulting in better performance (4772.17 calls/second for functions, 12125.03 calls/second for classes).
<!-- - Class tools show higher throughput due to more efficient method binding and reduced per-call overhead -->
- Process mode achieves true parallelism but has higher overhead, resulting in lower throughput compared to thread mode (2357.26 calls/second for functions, 3010.66 calls/second for classes).

#### Summary

- OpenAPI and MCP calls involve network I/O and event loop management; thread mode suffers from resource contention and event loop overhead, reducing performance.
- Process mode isolates resources, avoids contention, and improves network call throughput.
- Process mode achieves considerable proformance in tool_call use case and provides better safety railguard. Thus we generally recommend leave execution mode to `process` as default.
