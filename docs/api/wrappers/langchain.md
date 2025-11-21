# LangChainToolWrapper

Wrapper class providing both async and sync versions of LangChain tool calls.

## Overview

`LangChainToolWrapper` serves as the specialized wrapper for LangChain tools, providing seamless interoperability between LangChain's extensive tool ecosystem and the ToolRegistry's standardized interface. It preserves LangChain's original execution semantics while enabling integration with the broader ToolRegistry ecosystem.

## Key Features

- **LangChain Integration**: Direct compatibility with LangChain BaseTool instances
- **Execution Preservation**: Maintains LangChain's original async/sync execution behavior
- **Schema Conversion**: Automatic conversion between LangChain and ToolRegistry schemas
- **Error Transparency**: Preserves original LangChain exceptions with enhanced context
- **Parameter Mapping**: Seamless parameter handling between different schema formats
- **Async/Sync Bridge**: Full support for both synchronous and asynchronous execution

## Architecture

The LangChainToolWrapper extends `BaseToolWrapper` with LangChain-specific functionality:

### Core Components

1. **LangChain Tool Management**: Direct integration with LangChain BaseTool instances
2. **Schema Transformation**: Converts LangChain input schemas to ToolRegistry format
3. **Execution Bridge**: Preserves LangChain's _run() and _arun() methods
4. **Error Enhancement**: Maintains LangChain exceptions with additional context

### Integration Flow

```
ToolRegistry Tool Call
    ↓
Schema Mapping
    ↓
LangChain Tool Execution (_run/_arun)
    ↓
Result Processing
    ↓
ToolRegistry Response
```

## API Reference

::: toolregistry.langchain.integration.LangChainToolWrapper
    options:
      show_source: false
      show_root_heading: true
      show_root_toc_entry: false
      merge_init_into_class: true

## Usage Examples

### Basic LangChain Tool Wrapper

```python
from langchain_core.tools import BaseTool
from toolregistry.langchain.integration import LangChainToolWrapper

# Assume we have a LangChain tool
langchain_tool = BaseTool(
    name="calculator",
    description="Performs basic arithmetic operations",
    args_schema=CalculatorInput
)

# Create wrapper
wrapper = LangChainToolWrapper(tool=langchain_tool)

# Execute tool (automatic mode detection)
result = wrapper(a=5, b=3, operation="add")  # Sync - calls tool._run()
result = await wrapper(a=5, b=3, operation="add")  # Async - calls tool._arun()
```

### Custom LangChain Tool

```python
from langchain_core.tools import BaseTool, Tool
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")
    operation: str = Field(description="Operation to perform")

def calculate(a: float, b: float, operation: str) -> float:
    """Perform calculation based on operation."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    # ... other operations

# Create LangChain tool
langchain_tool = Tool(
    name="calculator",
    description="Performs basic arithmetic operations",
    func=calculate,
    args_schema=CalculatorInput
)

# Wrap in ToolRegistry
wrapper = LangChainToolWrapper(langchain_tool)
```

## Schema Conversion

The wrapper automatically converts LangChain schemas:

### LangChain Schema (Pydantic)
```python
class InputSchema(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(description="Result limit", default=10)
```

### ToolRegistry Schema (JSON)
```python
{
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer", "description": "Result limit", "default": 10}
    },
    "required": ["query"]
}
```

### Automatic Conversion
```python
# Wrapper handles the conversion automatically
langchain_tool = Tool(...)
wrapper = LangChainToolWrapper(langchain_tool)

# No manual schema conversion needed
result = wrapper(query="search term", limit=5)
```

## Execution Modes

### Synchronous Execution
```python
# Calls langchain_tool._run(*args, **kwargs)
wrapper = LangChainToolWrapper(langchain_tool)
result = wrapper(param1="value1", param2="value2")
```

### Asynchronous Execution
```python
# Calls langchain_tool._arun(*args, **kwargs)
wrapper = LangChainToolWrapper(langchain_tool)
result = await wrapper(param1="value1", param2="value2")
```

### Automatic Mode Detection
```python
import asyncio

# Detects execution context automatically
result1 = wrapper(arg="value")  # Sync context → _run()
result2 = await wrapper(arg="value")  # Async context → _arun()
```

## Integration Patterns

### With LangChain Integration

```python
from toolregistry import ToolRegistry
from toolregistry.langchain import LangChainIntegration

registry = ToolRegistry()
langchain_integration = LangChainIntegration(registry)

# Register single LangChain tool
await langchain_integration.register_langchain_tools_async(langchain_tool)

# Tool is automatically wrapped with LangChainToolWrapper
```

### Direct Wrapper Usage

```python
# For immediate tool wrapping
wrapper = LangChainToolWrapper(langchain_tool)

# Use directly or register in ToolRegistry
registry.register(wrapper)
```

## Error Handling

The wrapper preserves LangChain's original error handling:

### LangChain Exceptions
```python
# Original LangChain exceptions are preserved
from langchain_core.tools import ToolException

try:
    result = wrapper(invalid_param="value")
except ToolException as e:
    # Original LangChain exception with enhanced context
    print(f"LangChain Error: {e}")
```

### Enhanced Error Context
```python
try:
    result = wrapper(param="value")
except Exception as e:
    # Enhanced with wrapper context while preserving original
    logger.error(f"Error in {wrapper.name}: {traceback.format_exc()}")
    raise  # Original exception is re-raised
```

## Supported LangChain Tool Types

### Function Tools
```python
from langchain_core.tools import Tool

def my_function(input: str) -> str:
    return f"Processed: {input}"

tool = Tool(name="my_tool", func=my_function)
wrapper = LangChainToolWrapper(tool)
```

### Structured Tools
```python
from langchain_core.tools import StructuredTool

def structured_function(query: str, limit: int) -> List[str]:
    return ["result1", "result2"]

tool = StructuredTool.from_function(structured_function)
wrapper = LangChainToolWrapper(tool)
```

### BaseTool Subclasses
```python
from langchain_core.tools import BaseTool

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "Custom tool description"
    
    def _run(self, query: str) -> str:
        return f"Custom result: {query}"
    
    async def _arun(self, query: str) -> str:
        return f"Custom async result: {query}"

wrapper = LangChainToolWrapper(CustomTool())
```

## Integration Benefits

### Non-Invasive Integration
- Original LangChain tool behavior is preserved
- No modification to existing LangChain tools required
- Backward compatibility with LangChain applications

### ToolRegistry Benefits
- Unified interface for all tool types
- Namespace organization support
- Cross-framework tool discovery
- Enhanced error logging and debugging

The LangChainToolWrapper enables seamless integration of LangChain's rich tool ecosystem into the ToolRegistry framework, providing the best of both worlds: LangChain's proven tool implementations with ToolRegistry's standardized execution interface.