# Executor Backends

The `executor` package provides pluggable execution backends for running tool functions with concurrency, cancellation, and timeout support.

## Overview

The executor package operates on bare `Callable + dict` arguments with **zero imports** from toolregistry internals. `ToolRegistry.execute_tool_calls()` translates tool calls into this interface automatically.

### Architecture

```
ToolRegistry.execute_tool_calls()
    ↓
Extract callable + arguments from Tool
    ↓
backend.submit(fn, kwargs, timeout=...)
    ↓
ExecutionHandle (cancel, status, result, progress)
    ↓
Collect results → dict[str, str]
```

## Backends

### ThreadBackend

Thread-pool executor with **cooperative cancellation** via `ExecutionContext`.

```python
from toolregistry.executor import ThreadBackend

backend = ThreadBackend(max_workers=4)
handle = backend.submit(my_func, {"x": 1, "y": 2}, timeout=10.0)
result = handle.result()
backend.shutdown()
```

Features:

- Cooperative cancellation via `ExecutionContext`
- Progress reporting via `handle.on_progress(callback)`
- Automatic async-to-sync wrapping
- Auto-injection of `_ctx: ExecutionContext` parameter

### ProcessPoolBackend

Process-pool executor with **cloudpickle serialization** for true parallelism.

```python
from toolregistry.executor import ProcessPoolBackend

backend = ProcessPoolBackend(max_workers=4)
handle = backend.submit(my_func, {"x": 1, "y": 2}, timeout=10.0)
result = handle.result()
backend.shutdown()
```

Features:

- True parallel execution across processes
- Cloudpickle serialization for function transport
- Automatic async-to-sync wrapping
- Hard cancel via `future.cancel()` (no cooperative cancellation)

## ExecutionContext

Tool functions can opt into cooperative cancellation and progress reporting by declaring a `_ctx: ExecutionContext` parameter:

```python
from toolregistry.executor import ExecutionContext

def long_running_task(data: list, _ctx: ExecutionContext) -> str:
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # raises CancelledError if cancelled
        process(item)
        _ctx.report_progress(fraction=(i + 1) / len(data), message=f"Step {i+1}")
    return "done"
```

The backend auto-injects the context when it detects the `_ctx` parameter. Users do **not** pass it explicitly.

**Key methods:**

| Method | Description |
|--------|-------------|
| `cancelled` | Property: `True` if cancellation was requested |
| `check_cancelled()` | Raises `CancelledError` if cancelled |
| `report_progress(fraction, message, detail)` | Emit a progress update |

## ExecutionHandle

Returned by `backend.submit()`. Controls and observes a running execution.

| Method | Description |
|--------|-------------|
| `result(timeout)` | Block until result or timeout |
| `cancel()` | Request cancellation |
| `status()` | Return `ExecutionStatus` (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED) |
| `on_progress(callback)` | Register a progress listener |
| `execution_id` | Unique ID for this execution |

## ExecutionBackend Protocol

Custom backends can be created by implementing the `ExecutionBackend` protocol:

```python
from toolregistry.executor import ExecutionBackend, ExecutionHandle

class MyBackend:
    def submit(self, fn, kwargs, *, execution_id=None, timeout=None) -> ExecutionHandle:
        ...

    def shutdown(self, wait=True) -> None:
        ...
```

## Integration with ToolRegistry

Backends are used transparently via `ToolRegistry`:

```python
from toolregistry import ToolRegistry, ToolMetadata, Tool

registry = ToolRegistry()

# Set the default execution mode
registry.set_execution_mode("thread")  # or "process" (default)

# Per-call override
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")

# Timeout enforcement via ToolMetadata
tool = Tool.from_function(slow_func, metadata=ToolMetadata(timeout=5.0))
registry.register(tool)

# Concurrency safety control
tool = Tool.from_function(unsafe_func, metadata=ToolMetadata(is_concurrency_safe=False))
registry.register(tool)
# When any tool in a batch is not concurrency-safe, the entire batch runs sequentially
```
