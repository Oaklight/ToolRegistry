# Execution Backends and Async Support

???+ note "Changelog"
    - **Unreleased**: InlineBackend, `ainvoke` / `aexecute_tool_calls`, per-tool backend resolution, sync inline→thread promotion, `natural_backend`, `force_thread` removed
    - Refactored in version: 0.7.0 (pluggable executor backends)
    - New in version: 0.4.5

## Overview

ToolRegistry provides **three execution backends** and both **sync and async** entry points. The calling interface (sync/async) and the execution backend (inline/thread/process) are orthogonal — you pick the interface based on your context, and each tool resolves to its natural backend automatically.

### Backends

| Backend | Class | Isolation | Timeout | Best For |
|---------|-------|-----------|---------|----------|
| **Inline** | `InlineBackend` | None | ✅ async path (`wait_for`) | MCP, OpenAPI, tools already isolated externally |
| **Thread** | `ThreadBackend` | Thread | ✅ `Future.result(t)` | Sync callers, timeout enforcement, shared-memory tasks |
| **Process** | `ProcessPoolBackend` | Process | ✅ `Future.result(t)` | CPU isolation, fault isolation (cloudpickle) |

### Entry Points

| Entry Point | Returns | Backend default |
|-------------|---------|----------------|
| `invoke(name, kwargs)` | `ToolCallResult \| ErrorResult` | Inline tools → thread; others → inline |
| `ainvoke(name, kwargs)` | `ToolCallResult \| ErrorResult` | Inline tools → inline (native `await`) |
| `execute_tool_calls(tcs)` | `ResultList` | Per-tool: `natural_backend` → registry default (`process`) |
| `aexecute_tool_calls(tcs)` | `ResultList` | Per-tool: inline tools overlap on caller's loop |

All four entry points return structured `Result` types and **never raise** for access-control failures (missing, disabled, denied) — they return `ErrorResult` instead.

## Per-Tool Backend Resolution

The `_resolve_backend` seam resolves the backend **per tool**, not per batch:

```
1. Explicit caller execution_mode ("thread" / "process")  → wins
2. tool.metadata.natural_backend ("inline" / "thread" / "process")  → tool's preference
3. Context default  → inline for single calls, registry._execution_mode for batch
```

An additional rule applies: **on sync entry points, inline is promoted to thread** so that `Future.result(timeout)` gives a real deadline. Async entry points keep inline because they need the coroutine on their own event loop.

### `natural_backend`

MCP and OpenAPI tools automatically set `natural_backend="inline"` at registration — their live connections (MCP `ClientSession`, httpx sockets) are event-loop-bound and cannot be pickled into a process pool. PTC's `programmatic_tool_call` tool also uses `natural_backend="inline"` because its IPC callbacks must stay in the calling process.

```python
from toolregistry import Tool, ToolMetadata

# Explicitly set a tool's preferred backend
tool = Tool.from_function(my_func, metadata=ToolMetadata(natural_backend="thread"))
registry.register(tool)
```

## Async Support

### `ainvoke`

Async counterpart to `invoke()`. For inline-resolved tools (MCP, OpenAPI, async native functions), the coroutine is awaited directly on the caller's event loop — no thread hop, no `asyncio.run()`:

```python
result = await registry.ainvoke("mcp_tool", {"query": "hello"})
assert isinstance(result, ToolCallResult)
```

### `aexecute_tool_calls`

Async batch execution via `asyncio.gather`. Inline tools overlap on the caller's loop; pool-backed tools submit and `await handle.result_async()`:

```python
results = await registry.aexecute_tool_calls(tool_calls)
```

Concurrency-safe tools run concurrently; if any tool has `is_concurrency_safe=False`, the entire batch runs sequentially (same as the sync path).

## Inline Backend

Runs the target in the current context with no pool. Uses **lazy capture** — `submit()` stores the callable; execution is deferred to `result()` (sync) or `result_async()` (async).

- **Async path**: `result_async()` awaits the coroutine natively. Timeout is enforced via `asyncio.wait_for`.
- **Sync path**: On sync entry points, inline-resolved tools are **promoted to the thread backend**, so they get real timeout via `Future.result(timeout)`. This promotion is handled transparently by `_resolve_backend`.

The inline backend is suited to tools that are already isolated elsewhere (MCP servers run in their own process; OpenAPI tools are pure HTTP) — pooling or pickling their transport would be wrong or impossible.

## Thread Backend

Uses `concurrent.futures.ThreadPoolExecutor` with cooperative cancellation via `ExecutionContext`.

**Advantages:**

- Lower overhead for CPU-bound local functions
- Shared memory — no serialization needed
- Cooperative cancellation and progress reporting
- Real timeout via `Future.result(timeout)`

**Limitations:**

- Subject to the GIL for CPU-bound parallelism

### Cooperative Cancellation

Tool functions can opt into cooperative cancellation by accepting an `_ctx` parameter:

```python
from toolregistry.executor import ExecutionContext

def long_task(data: list, _ctx: ExecutionContext) -> str:
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # raises CancelledError if cancelled
        process(item)
        _ctx.report_progress(fraction=(i + 1) / len(data))
    return "done"
```

## Process Backend (Batch Default)

Uses a process pool with **cloudpickle** serialization for true parallelism.

**Advantages:**

- Independent memory spaces — crash isolation
- No GIL — true parallel execution

**Limitations:**

- Higher overhead from inter-process communication
- No cooperative cancellation
- Functions and arguments must be picklable
- MCP/OpenAPI tools **cannot** use this backend (live connections are non-picklable)

## Switching Modes

### Permanent Change

```python
registry.set_default_execution_mode("thread")  # or "process" (default)
```

### Per-Call Override

```python
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
result = registry.invoke("tool", args, execution_mode="process")
```

## Timeout

Per-tool timeout is set via `ToolMetadata.timeout`:

```python
tool = Tool.from_function(slow_func, metadata=ToolMetadata(timeout=5.0))
```

Timeout enforcement depends on the path:

| Entry Point | Backend | Enforced? | Mechanism |
|-------------|---------|-----------|-----------|
| `invoke()` | thread (promoted) | ✅ | `Future.result(timeout)` |
| `ainvoke()` | inline | ✅ | `asyncio.wait_for` |
| `execute_tool_calls()` | thread/process | ✅ | `Future.result(timeout)` |
| `aexecute_tool_calls()` | inline | ✅ | `asyncio.wait_for` |

## Sequential Execution

Mark a tool as not concurrency-safe to force the entire batch to run sequentially:

```python
tool = Tool.from_function(
    unsafe_func,
    metadata=ToolMetadata(is_concurrency_safe=False),
)
```

## See Also

- [Architecture Overview](../architecture/overview.md) — execution stack diagram
- [Executor Backends API Reference](../api/core/executor.md) — `InlineBackend`, `ThreadBackend`, `ProcessPoolBackend`, `ExecutionHandle`
