# Execution Modes: Thread and Process

???+ note "Changelog"
    - Refactored in version: 0.7.0 (pluggable executor backends)
    - New in version: 0.4.5

## Overview

ToolRegistry executes tool calls concurrently using pluggable **executor backends**. Two backends are provided:

| Backend | Class | Best For |
|---------|-------|----------|
| **Thread** | `ThreadBackend` | Lightweight CPU-bound tasks, shared-memory scenarios |
| **Process** | `ProcessPoolBackend` | Network I/O (MCP, OpenAPI), crash isolation |

Process mode is the **default** — it provides better isolation and higher throughput for network-bound tools.

## How It Works

When `execute_tool_calls()` is invoked, ToolRegistry routes each call through the selected backend:

```
execute_tool_calls(tool_calls)
    ↓
Extract callable + arguments from each Tool
    ↓
backend.submit(fn, kwargs, timeout=...)  →  ExecutionHandle
    ↓
Collect results → dict[str, str]
```

Each submission returns an `ExecutionHandle` that supports cancellation, status queries, and progress callbacks. See the [Executor API reference](../api/core/executor.md) for backend and handle details.

## Thread Mode

Uses a thread pool (`concurrent.futures.ThreadPoolExecutor`) with cooperative cancellation via `ExecutionContext`.

**Advantages:**

- Lower overhead for CPU-bound local functions
- Shared memory — no serialization needed
- Cooperative cancellation and progress reporting

**Limitations:**

- Subject to the GIL for CPU-bound parallelism
- Shared memory can lead to corruption or contention under heavy concurrent I/O

## Process Mode (Default)

Uses a process pool with **cloudpickle** serialization for true parallelism.

**Advantages:**

- Independent memory spaces — crash isolation between tool calls
- No GIL — true parallel execution
- Better throughput for network I/O (MCP, OpenAPI) due to isolated event loops

**Limitations:**

- Higher overhead from inter-process communication and serialization
- No cooperative cancellation (uses `future.cancel()` hard-cancel)
- Functions and arguments must be picklable

## Switching Modes

### Permanent Change

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.set_execution_mode("thread")  # or "process" (default)
```

### Per-Call Override

```python
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
```

## Controlling Concurrency via ToolMetadata

### Timeout Enforcement

Set a per-tool timeout via `ToolMetadata`. The backend enforces it automatically:

```python
from toolregistry import Tool, ToolMetadata

tool = Tool.from_function(slow_func, metadata=ToolMetadata(timeout=5.0))
registry.register(tool)
# If slow_func takes longer than 5 seconds, it will be cancelled/timed out
```

### Sequential Execution

Mark a tool as not concurrency-safe to force the entire batch to run sequentially:

```python
tool = Tool.from_function(
    unsafe_func,
    metadata=ToolMetadata(is_concurrency_safe=False),
)
registry.register(tool)
# When any tool in a batch has is_concurrency_safe=False,
# the entire batch executes sequentially
```

### Cooperative Cancellation (Thread Mode)

Tool functions can opt into cooperative cancellation by accepting an `_ctx` parameter. The backend auto-injects it:

```python
from toolregistry.executor import ExecutionContext

def long_task(data: list, _ctx: ExecutionContext) -> str:
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # raises CancelledError if cancelled
        process(item)
        _ctx.report_progress(fraction=(i + 1) / len(data), message=f"Step {i+1}")
    return "done"
```

!!! note
    `ExecutionContext` is only supported with `ThreadBackend`. In process mode, cancellation is handled via `future.cancel()`.

## Performance Characteristics

The following benchmarks compare thread and process modes across different tool types (100 concurrent calls each):

| Tool Type | Thread Mode | Process Mode |
|-----------|------------|--------------|
| Native Function | 4772 calls/s | 2357 calls/s |
| Native Class | 12125 calls/s | 3011 calls/s |
| OpenAPI (network) | 28 calls/s | 451 calls/s |
| MCP SSE (network) | 27 calls/s | 132 calls/s |

**Key takeaways:**

- **Local functions**: Thread mode wins due to lower overhead (no serialization, no IPC)
- **Network I/O (OpenAPI, MCP)**: Process mode wins dramatically (5-16x) because each process gets its own event loop and network connections, eliminating contention
- **Default recommendation**: Use process mode unless your workload is purely local CPU-bound functions

## See Also

- [Executor Backends API Reference](../api/core/executor.md) — `ThreadBackend`, `ProcessPoolBackend`, `ExecutionContext`, `ExecutionHandle`
- [Tool Metadata & Tags](permissions.md#toolmetadata-fields) — `timeout`, `is_concurrency_safe`
