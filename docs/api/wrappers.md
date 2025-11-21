# Tool Wrappers

This section documents the various tool wrapper classes that provide standardized interfaces for different tool types within the ToolRegistry ecosystem.

## Overview

Tool wrappers serve as adapters that translate between external tool formats and the ToolRegistry's standardized interface. Each wrapper is specialized for a specific integration type while maintaining consistent execution semantics.

## Available Wrappers

### Base Classes

- [**BaseToolWrapper**](wrappers/basetoolwrapper.md): Abstract base class for all tool wrappers
  - Provides common interface for sync/async execution
  - Handles parameter processing and validation
  - Implements automatic execution mode detection

### Framework-Specific Wrappers

- [**MCPToolWrapper**](wrappers/mcp.md): MCP server tool wrapper

  - Handles Model Context Protocol communication
  - Supports various content types (text, image, embedded)
  - Manages transport abstraction for different connection types

- [**OpenAPIToolWrapper**](wrappers/openapi.md): OpenAPI tool wrapper

  - Provides HTTP client functionality for REST APIs
  - Supports multiple HTTP methods (GET, POST, PUT, DELETE)
  - Handles parameter processing and error management

- [**LangChainToolWrapper**](wrappers/langchain.md): LangChain tool wrapper
  - Bridges LangChain tools with ToolRegistry interface
  - Preserves LangChain's original execution semantics
  - Supports both synchronous and asynchronous modes

## Common Patterns

All tool wrappers follow these common patterns:

### Interface Standardization

```python
class ExampleWrapper(BaseToolWrapper):
    def call_sync(self, *args, **kwargs) -> Any:
        """Synchronous execution."""
        pass

    async def call_async(self, *args, **kwargs) -> Any:
        """Asynchronous execution."""
        pass
```

### Parameter Processing

```python
# Automatic argument mapping
wrapper = ExampleWrapper("tool_name", params=["param1", "param2"])

# These calls are equivalent:
wrapper("value1", "value2")
wrapper(param1="value1", param2="value2")
```

### Automatic Mode Detection

```python
# Wrapper automatically selects appropriate execution mode
result1 = wrapper(arg1="value1")  # Sync context → call_sync()
result2 = await wrapper(arg1="value1")  # Async context → call_async()
```

## Architecture

Tool wrappers follow the Adapter pattern:

```
External Tool → Wrapper → ToolRegistry Interface
```

This design allows:

- **Consistent API**: All tools expose the same interface regardless of source
- **Framework Preservation**: Original tool behavior is maintained
- **Execution Flexibility**: Support for both sync and async execution
- **Error Transparency**: Original exceptions are preserved with additional context

## Wrapper Selection Guide

### Choose MCPToolWrapper when:

- Working with Model Context Protocol servers
- Need support for various content types (text, images, files)
- Require transport abstraction (HTTP, WebSocket, file-based)

### Choose OpenAPIToolWrapper when:

- Integrating RESTful APIs
- Need HTTP method support (GET, POST, PUT, DELETE)
- Require HTTP client functionality and error handling

### Choose LangChainToolWrapper when:

- Integrating existing LangChain tools
- Need to preserve LangChain's execution semantics
- Want automatic schema conversion between frameworks

## Integration Points

Wrappers integrate with:

- **Tool Classes**: Wrappers are used by specialized Tool classes
- **ToolRegistry**: Tools with wrappers are registered in the registry
- **LLM Applications**: Consistent interface for LLM tool calling
- **Async Frameworks**: Full compatibility with async/await patterns

Each wrapper is designed to be framework-specific while maintaining the same execution contract, enabling seamless tool discovery and execution across different LLM applications.
