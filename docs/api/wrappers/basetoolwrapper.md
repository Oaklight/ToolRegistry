# BaseToolWrapper

Base class for tool wrappers that provide support for synchronous and asynchronous calls within the ToolRegistry ecosystem.

## Overview

`BaseToolWrapper` serves as the foundational abstract base class for all tool wrappers in the ToolRegistry system. It provides a standardized interface for executing tools with both synchronous and asynchronous capabilities, ensuring consistent behavior across different tool types and integration frameworks.

## Key Features

- **Abstract Interface**: Defines the core contract for tool execution
- **Dual Execution Modes**: Support for both synchronous and asynchronous tool execution
- **Automatic Mode Detection**: Automatically selects appropriate execution mode based on runtime context
- **Parameter Processing**: Built-in argument processing for positional and keyword arguments
- **Standardized Metadata**: Consistent handling of tool names and parameter lists

## Architecture

The BaseToolWrapper follows the Template Method pattern with the following design:

### Abstract Methods

1. **call_sync()**: Must be implemented by subclasses for synchronous execution
2. **call_async()**: Must be implemented by subclasses for asynchronous execution

### Concrete Methods

1. \***\*call**()\*\*: Automatically selects between sync and async execution
2. **\_process_args()**: Processes and validates positional and keyword arguments

### Execution Flow

```
User calls wrapper()
    ↓
Auto-detect execution context
    ↓
Call call_sync() or call_async()
    ↓
Execute underlying tool logic
    ↓
Return result
```

## API Reference

::: toolregistry.tool_wrapper.BaseToolWrapper
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Usage Examples

### Basic Wrapper Implementation

```python
from toolregistry.tool_wrapper import BaseToolWrapper
from typing import Any, List, Optional

class CustomToolWrapper(BaseToolWrapper):
    def __init__(self, name: str, tool_function: callable, params: Optional[List[str]] = None):
        super().__init__(name=name, params=params)
        self.tool_function = tool_function

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous tool execution."""
        processed_kwargs = self._process_args(*args, **kwargs)
        return self.tool_function(**processed_kwargs)

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronous tool execution."""
        processed_kwargs = self._process_args(*args, **kwargs)
        # Assuming tool_function supports async execution
        return await self.tool_function(**processed_kwargs)
```

### Usage with Custom Tool

```python
def my_calculator(a: int, b: int) -> int:
    """Simple calculator function."""
    return a + b

# Create wrapper
wrapper = CustomToolWrapper(
    name="calculator",
    tool_function=my_calculator,
    params=["a", "b"]
)

# Automatic mode selection
result1 = wrapper(a=5, b=3)  # Sync execution
result2 = await wrapper(a=5, b=3)  # Async execution
```

## Parameter Processing

The BaseToolWrapper provides sophisticated parameter processing:

### Argument Validation

```python
# Positional arguments are mapped to parameter names
wrapper = BaseToolWrapper("test", params=["param1", "param2"])

# These calls are equivalent:
wrapper("value1", "value2")
wrapper(param1="value1", param2="value2")
```

### Error Handling

- **Parameter Count Validation**: Ensures no more arguments than defined parameters
- **Duplicate Argument Detection**: Prevents passing same parameter as both positional and keyword
- **Missing Parameter Handling**: Allows optional parameters when not all are required

## Execution Context Detection

The wrapper automatically detects the appropriate execution mode:

```python
import asyncio

# Sync context
result = wrapper(a=1, b=2)  # Calls call_sync()

# Async context
async def async_context():
    result = await wrapper(a=1, b=2)  # Calls call_async()
```

## Subclassing Guidelines

When creating subclasses, implement these patterns:

1. **Initialization**: Call `super().__init__()` with name and parameters
2. **Sync Implementation**: Handle synchronous execution in `call_sync()`
3. **Async Implementation**: Handle asynchronous execution in `call_async()`
4. **Parameter Validation**: Use `_process_args()` for argument processing
5. **Error Handling**: Preserve original exception behavior

## Integration

BaseToolWrapper is used by all integration modules:

- **OpenAPI**: OpenAPIToolWrapper
- **MCP**: MCPToolWrapper
- **LangChain**: LangChainToolWrapper
- **Native**: Native function wrappers

This ensures consistent execution semantics across all tool types within the ToolRegistry ecosystem.
