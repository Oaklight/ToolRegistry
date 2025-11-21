# ToolRegistry

The central registry class that manages tool registration, execution, and metadata across the ToolRegistry ecosystem.

## Overview

`ToolRegistry` serves as the core orchestrator for tool management in the ToolRegistry library. It provides a unified interface for registering, discovering, and executing tools from various sources including native Python functions, OpenAPI specifications, MCP servers, LangChain tools, and more.

## Key Features

- **Unified Tool Management**: Central registry for all types of tools
- **Async/Sync Support**: Full compatibility with both synchronous and asynchronous execution
- **Namespace Organization**: Support for organizing tools under namespaces
- **Multi-Source Integration**: Seamless integration with various tool sources
- **Metadata Preservation**: Maintains tool descriptions, parameters, and execution metadata
- **Flexible Execution**: Multiple execution modes and concurrency options

## Architecture

The ToolRegistry follows a registry pattern with the following key responsibilities:

### Core Responsibilities

1. **Tool Registration**: Accept and register tools from various sources
2. **Tool Discovery**: Provide mechanisms to discover available tools
3. **Tool Execution**: Execute tools with proper parameter validation and error handling
4. **Metadata Management**: Maintain and provide access to tool metadata
5. **Namespace Support**: Organize tools under logical namespaces

### Registration Methods

- **Native Registration**: `register()` for direct function/instance registration
- **Class Integration**: `register_from_class()` for Python class method registration
- **OpenAPI Integration**: Integration with OpenAPI specifications
- **MCP Integration**: Support for Model Context Protocol servers
- **LangChain Integration**: Compatibility with LangChain tools

### Execution Models

- **Synchronous Execution**: Direct tool execution for non-async tools
- **Asynchronous Execution**: Async/await support for async tools
- **Concurrent Execution**: Support for parallel tool execution
- **Error Handling**: Comprehensive error handling and logging

## API Reference

::: toolregistry.ToolRegistry
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true
separate_signature: true
show_signature_annotations: true

## Usage Examples

### Basic Tool Registration

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Register a simple function
def add_numbers(a: int, b: int) -> int:
    return a + b

registry.register(add_numbers)
```

### Class Integration

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

class Calculator:
    @staticmethod
    def multiply(a: int, b: int) -> int:
        return a * b

    def divide(self, a: int, b: int) -> float:
        return a / b

# Register all methods from the class
registry.register_from_class(Calculator)
```

### Namespace Organization

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# Register with custom namespace
registry.register(my_function, namespace="math_utils")

# Access tools with namespace
available_tools = registry.get_available_tools(namespace="math_utils")
```

## Integration Points

The ToolRegistry provides integration points for:

- **OpenAPI Services**: Automatic REST API tool generation
- **MCP Servers**: Model Context Protocol tool discovery
- **LangChain Tools**: LangChain ecosystem integration
- **Native Python**: Direct class and function registration

This makes it a central hub for managing tools from diverse sources within LLM applications.
