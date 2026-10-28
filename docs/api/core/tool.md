# Tool

Represents an individual tool with metadata and execution logic within the ToolRegistry ecosystem.

## Overview

The `Tool` class serves as a fundamental abstraction for all tools in the ToolRegistry system. It encapsulates both the executable logic and the metadata necessary for proper tool discovery, parameter validation, and execution within LLM applications.

## Key Features

- **Metadata Management**: Comprehensive tool description, parameters, and execution metadata
- **Parameter Validation**: Built-in parameter schema validation and type checking
- **Execution Abstraction**: Unified interface for both synchronous and asynchronous execution
- **Namespace Support**: Integration with namespace organization for tool grouping
- **Callable Integration**: Direct execution through callable interface

## Architecture

The Tool class follows a data-transfer-object pattern with the following key components:

### Core Attributes

1. **name**: Unique identifier for the tool
2. **description**: Human-readable description of tool functionality
3. **parameters**: JSON schema defining expected parameters
4. **callable**: The actual executable function or wrapper
5. **is_async**: Flag indicating asynchronous execution capability
6. **namespace**: Optional namespace for organization (stores the original namespace string after normalization)
7. **method_name**: Optional original method/function name before namespace prefixing (preserved for unambiguous base name recovery)

### Computed Properties

- **qualified_name**: Returns the registered `name`. The name is authoritative and is rebuilt from `namespace`, `method_name`, and the registry's separator by namespace operations.

### Design Philosophy

- **Immutability**: `Tool` and `ToolMetadata` are `frozen=True` dataclasses — fields cannot be reassigned after construction. `ToolMetadata` copies its `tags`, `custom_tags` and `extra` containers when constructed, so `dataclasses.replace()` copies are independent. Use `dataclasses.replace()` to create modified copies, or `Tool.with_parameters()` when replacing a parameter schema.
- **Schema-Driven**: Parameter validation based on JSON Schema standards
- **Execution Flexibility**: Support for both sync and async execution patterns
- **Metadata Preservation**: Complete preservation of tool metadata for LLM consumption

## API Reference

::: toolregistry.Tool
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## Usage Examples

### Basic Tool Creation

```python
from toolregistry import Tool

def calculate_area(length: float, width: float) -> float:
    """Calculate the area of a rectangle."""
    return length * width

# Create a Tool instance
area_tool = Tool(
    name="calculate_area",
    description="Calculate the area of a rectangle",
    parameters={
        "type": "object",
        "properties": {
            "length": {"type": "number", "description": "Length of rectangle"},
            "width": {"type": "number", "description": "Width of rectangle"}
        },
        "required": ["length", "width"]
    },
    callable=calculate_area,
    is_async=False
)
```

### Tool with Namespace

```python
from toolregistry import Tool

# Create a tool with namespace and method_name fields
math_tool = Tool(
    name="math_ops-multiply",
    description="Multiply two numbers",
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"}
        },
        "required": ["a", "b"]
    },
    callable=lambda a, b: a * b,
    is_async=False,
    namespace="math_ops",
    method_name="multiply",
)

# Access the qualified name
print(math_tool.qualified_name)  # Output: "math_ops-multiply"
print(math_tool.namespace)       # Output: "math_ops"
print(math_tool.method_name)     # Output: "multiply"
```

### Tool from Function with Namespace

```python
from toolregistry import Tool

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

# Create a tool with namespace using from_function()
tool = Tool.from_function(multiply, namespace="math_ops")
print(tool.name)            # Output: "math_ops-multiply"
print(tool.namespace)       # Output: "math_ops"
print(tool.method_name)     # Output: "multiply"
print(tool.qualified_name)  # Output: "math_ops-multiply"

# You can also provide a custom method_name
tool2 = Tool.from_function(multiply, namespace="math_ops", method_name="mul")
print(tool2.name)            # Output: "math_ops-mul"
print(tool2.method_name)     # Output: "mul"

# Use the registry's separator when constructing directly
tool3 = Tool.from_function(multiply, namespace="math_ops", sep=".")
print(tool3.name)            # Output: "math_ops.multiply"
```

When the registry uses `ToolRegistry(name_sep=".")`, pass the same separator
to `Tool.from_function(..., sep=".")` so the constructed name matches the
registry key.

### Updating Namespace

```python
from toolregistry import Tool

# Create a tool without namespace
math_tool = Tool.from_function(lambda a, b: a * b, name="multiply")

# Update with namespace
math_tool = math_tool.update_namespace("math_operations")
print(math_tool.name)           # Output: "math_operations-multiply"
print(math_tool.namespace)      # Output: "math_operations"
print(math_tool.method_name)    # Output: "multiply"
print(math_tool.qualified_name) # Output: "math_operations-multiply"
```

### Refreshing Metadata

```python
from toolregistry import Tool

tool = Tool.from_function(lambda x: x, name="echo")

# Update last_refreshed_at timestamp (returns a new frozen Tool)
updated = tool.with_refreshed_at("2026-09-15T08:00:00Z")
print(updated.metadata.last_refreshed_at)  # "2026-09-15T08:00:00Z"
```

### Execution Hints

`Tool.execution_hints` resolves hints for every tool, deriving `read_only_hint` / `destructive_hint` from `ToolTag.READ_ONLY` / `ToolTag.DESTRUCTIVE`. Those tags also drive the built-in permission rules, so the resolved mapping is not automatically safe to publish: a tag chosen for local policy would become a client-facing auto-approve claim.

`Tool.declared_execution_hints` returns only what the tool declared explicitly, plus the `destructive_hint=False` complement implied by an explicit `read_only_hint=True`. Transports should publish this mapping and treat an empty result as "no claim" (absent annotations), which is what an MCP client interprets as write-capable.

```python
from toolregistry import Tool
from toolregistry.tool import ToolMetadata, ToolTag

tagged = Tool.from_function(
    lambda: "state",
    name="reader",
    metadata=ToolMetadata(tags={ToolTag.READ_ONLY}),
)
print(tagged.execution_hints)          # {'read_only_hint': True, 'destructive_hint': False}
print(tagged.declared_execution_hints) # {}

explicit = Tool.from_function(
    lambda: "state",
    name="reader2",
    metadata=ToolMetadata(read_only_hint=True),
)
print(explicit.declared_execution_hints)  # {'read_only_hint': True, 'destructive_hint': False}
```

### Replacing a Parameter Schema

`dataclasses.replace(tool, parameters=...)` reuses the existing metadata, so the fingerprint would still describe the old schema. It now warns when that happens. Use `Tool.with_parameters()` to replace the schema and recompute the hash in one step:

```python
from toolregistry.utils import compute_schema_hash

updated = tool.with_parameters(
    {"type": "object", "properties": {"q": {"type": "string"}}}
)
assert updated.metadata.schema_hash == compute_schema_hash(updated.parameters)
```

The old validation model is dropped by default, because it describes the old schema, and a `UserWarning` names the tool when that happens; pass `parameters_model=` when the new schema is equivalent.

### Async Tool

```python
import asyncio
from toolregistry import Tool

async def fetch_data(url: str) -> dict:
    """Fetch data from a URL asynchronously."""
    # Async implementation
    return {"url": url, "data": "sample"}

# Create async tool
async_tool = Tool(
    name="fetch_data",
    description="Fetch data from URL",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch from"}
        },
        "required": ["url"]
    },
    callable=fetch_data,
    is_async=True
)
```

### Executing Tools

The `Tool` class provides sync and async execution:

- **`run(parameters)`** — Execute synchronously. Raises exceptions on failure.
- **`arun(parameters)`** — Execute asynchronously. Raises exceptions on failure.

Both methods handle sync/async callable transparency automatically. A sync tool can be called via `arun()` (dispatched via `asyncio.to_thread()`), and an async tool can be called via `run()` (dispatched via `asyncio.run()`).

```python
from toolregistry import Tool

def divide(a: float, b: float) -> float:
    """Divide a by b."""
    return a / b

tool = Tool.from_function(divide)

# Sync execution
try:
    result = tool.run({"a": 10, "b": 0})
except ZeroDivisionError:
    print("Cannot divide by zero!")

# Async execution
result = await tool.arun({"a": 10, "b": 2})  # returns 5.0
```

!!! note "`run_raw()` / `arun_raw()` are deprecated"
    These methods are now aliases for `run()` / `arun()` and emit
    `DeprecationWarning`. Use `run()` / `arun()` directly.

### Accessing the Underlying Function

Use the `tool.fn` property to get the original unwrapped function:

```python
tool = Tool.from_function(my_func)
tool.fn          # → my_func (the original function)
tool.callable    # → _FunctionToolWrapper (the wrapper, for internal use)
```

## Parameter Schema Format

The Tool class uses JSON Schema format for parameter validation:

```json
{
  "type": "object",
  "properties": {
    "param_name": {
      "type": "string|number|boolean|array|object",
      "description": "Parameter description",
      "default": "default_value"
    }
  },
  "required": ["param1", "param2"]
}
```

## Integration with ToolRegistry

Tools are primarily used through the ToolRegistry:

```python
from toolregistry import ToolRegistry, Tool

registry = ToolRegistry()

# Register tool with registry
registry.register(tool_instance)

# Execute tool through registry
result = registry.execute_tool("tool_name", param1="value1", param2="value2")
```

The Tool class provides the foundation for all tool operations within the ToolRegistry ecosystem, ensuring consistent behavior across different tool sources and execution environments.
