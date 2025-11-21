# Executor

Handles the execution of tool calls with support for different concurrency modes and parallel execution strategies.

## Overview

The `Executor` class serves as the core execution engine for the ToolRegistry system, providing efficient parallel tool execution with support for both thread-based and process-based concurrency. It handles the complexity of concurrent tool execution while maintaining thread safety and proper resource management.

## Key Features

- **Dual Execution Modes**: Support for both thread-pool and process-pool execution
- **Automatic Serialization**: Uses dill for function serialization across process boundaries
- **Async/Sync Bridge**: Automatic conversion of async functions to sync execution
- **Error Handling**: Comprehensive error handling and result serialization
- **Resource Management**: Automatic cleanup of executor pools on shutdown
- **Fallback Support**: Graceful fallback from process to thread execution

## Architecture

The Executor follows a strategy pattern for concurrent execution:

### Core Components

1. **Process Pool Executor**: For CPU-bound tasks and true parallel execution
2. **Thread Pool Executor**: For I/O-bound tasks and lightweight concurrency
3. **Execution Mode Management**: Dynamic switching between execution strategies
4. **Function Serialization**: dill-based serialization for cross-process execution

### Execution Flow

```
Tool Call Request
    ↓
Function Serialization (if process mode)
    ↓
Executor Pool Selection
    ↓
Parallel Execution
    ↓
Result Collection & Serialization
    ↓
Response Mapping
```

## API Reference

::: toolregistry.executor.Executor
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Usage Examples

### Basic Executor Setup

```python
from toolregistry.executor import Executor

# Create executor instance
executor = Executor()

# Set execution mode
executor.set_execution_mode("process")  # or "thread"
```

### Tool Execution

```python
import json
from toolregistry.executor import Executor
from toolregistry.types import ToolCall

def get_tool_function(tool_name: str):
    """Function to retrieve tool by name."""
    # Implementation depends on your tool registry
    pass

# Prepare tool calls
tool_calls = [
    ToolCall(id="call_1", name="calculate", arguments='{"a": 5, "b": 3}'),
    ToolCall(id="call_2", name="multiply", arguments='{"x": 4, "y": 2}'),
]

# Execute tool calls
executor = Executor()
results = executor.execute_tool_calls(get_tool_function, tool_calls)

# Results: {"call_1": "8", "call_2": "8"}
```

### Async Function Support

```python
import asyncio
from toolregistry.executor import Executor

async def async_calculator(a: int, b: int) -> int:
    """Async calculation function."""
    await asyncio.sleep(0.1)  # Simulate async work
    return a + b

# Async functions are automatically converted to sync
# when executed through the executor
```

## Execution Modes

### Process Mode

- **Use Case**: CPU-bound tasks, true parallel execution
- **Pros**: True parallelism, memory isolation
- **Cons**: Higher overhead, serialization required
- **Best For**: Mathematical computations, data processing

### Thread Mode

- **Use Case**: I/O-bound tasks, lightweight concurrency
- **Pros**: Lower overhead, shared memory
- **Cons**: GIL limitations, less true parallelism
- **Best For**: API calls, file operations, database queries

## Configuration

### Mode Selection

```python
# Dynamic mode setting
executor.set_execution_mode("thread")  # Switch to thread mode

# Per-execution mode override
results = executor.execute_tool_calls(
    get_tool_fn,
    tool_calls,
    execution_mode="process"
)
```

### Resource Management

```python
# Automatic cleanup on program exit
# Manual shutdown (rarely needed)
executor._shutdown_executors()
```

## Error Handling

The executor provides robust error handling:

- **Serialization Errors**: Graceful handling of non-serializable functions
- **Execution Errors**: Individual tool call failures don't crash other executions
- **Fallback Mechanisms**: Automatic fallback from process to thread execution
- **Result Serialization**: Automatic conversion of non-JSON results to strings

## Integration

The Executor integrates with:

- **ToolRegistry**: Primary execution engine for tool calls
- **Tool Classes**: Works with any Tool implementation
- **LLM Applications**: Handles tool calls from language models
- **Async Frameworks**: Bridges async/sync execution boundaries

This makes it the central execution component that enables efficient, concurrent tool execution across the entire ToolRegistry ecosystem.
