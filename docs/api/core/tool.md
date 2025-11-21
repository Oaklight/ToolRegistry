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
6. **namespace**: Optional namespace for organization

### Design Philosophy

- **Immutability**: Tool instances are designed to be immutable after creation
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

# Create a tool with namespace
math_tool = Tool(
    name="multiply",
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
    is_async=False
)

# Update with namespace
math_tool.update_namespace("math_operations")
print(math_tool.name)  # Output: "math_operations.multiply"
```

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
