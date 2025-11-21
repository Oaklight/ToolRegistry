# MCPToolWrapper

Wrapper class providing both async and sync versions of MCP (Model Context Protocol) tool calls.

## Overview

`MCPToolWrapper` serves as the specialized wrapper for Model Context Protocol (MCP) servers, providing seamless communication between ToolRegistry and MCP-based tools. It handles the complexities of MCP protocol communication, including various content types, transport management, and error handling.

## Key Features

- **MCP Protocol Integration**: Full support for Model Context Protocol specification
- **Multi-Transport Support**: Handles different transport types (HTTP, WebSocket, file-based)
- **Content Type Handling**: Support for text, image, and embedded resource content
- **Transport Abstraction**: Transparent management of ClientTransport instances
- **Error Resilience**: Comprehensive error handling with detailed logging
- **Async/Sync Compatibility**: Both asynchronous and synchronous execution modes

## Architecture

The MCPToolWrapper extends `BaseToolWrapper` with MCP-specific functionality:

### Core Components

1. **Transport Management**: Handles ClientTransport lifecycle and communication
2. **Content Processing**: Processes various MCP content types (text, image, embedded)
3. **Protocol Handling**: Manages MCP tool discovery and execution
4. **Error Handling**: Preserves MCP errors with enhanced context

### Communication Flow

```
Tool Call Request
    ↓
Parameter Validation
    ↓
MCP Client Communication
    ↓
Content Type Processing
    ↓
Result Normalization
    ↓
ToolRegistry Response
```

## API Reference

::: toolregistry.mcp.integration.MCPToolWrapper
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Usage Examples

### Basic MCP Tool Wrapper

```python
from fastmcp.client import ClientTransport
from toolregistry.mcp.integration import MCPToolWrapper

# Create MCP transport
transport = ClientTransport("ws://localhost:8000")

# Create wrapper for specific MCP tool
wrapper = MCPToolWrapper(
    transport=transport,
    name="mcp_calculator",
    params=["a", "b", "operation"]
)

# Execute tool (automatic mode detection)
result = wrapper(a=5, b=3, operation="add")  # Sync
result = await wrapper(a=5, b=3, operation="add")  # Async
```

### Content Type Processing

```python
# Handle different MCP content types
wrapper = MCPToolWrapper(transport, "document_processor", params=["file_path"])

# Text content
result = wrapper(file_path="readme.txt")  # Returns string content

# Image content
result = wrapper(file_path="image.png")  # Returns {"type": "image", "data": ..., "mimeType": "..."}

# Embedded resources
result = wrapper(file_path="data.json")  # Returns parsed JSON or resource content
```

## Content Type Support

The wrapper handles multiple MCP content types:

### Text Content

```python
# Simple text response
{
    "result": "Calculation completed: 5 + 3 = 8"
}
```

### Image Content

```python
# Image response
{
    "result": {
        "type": "image",
        "data": "base64_encoded_image_data",
        "mimeType": "image/png"
    }
}
```

### Embedded Resources

```python
# Embedded text resource
{
    "result": "Embedded file content"
}

# Embedded blob resource
{
    "result": {
        "type": "blob",
        "data": "binary_data",
        "mimeType": "application/octet-stream"
    }
}
```

## Integration Patterns

### With MCP Integration

```python
from toolregistry import ToolRegistry
from toolregistry.mcp import MCPIntegration

registry = ToolRegistry()
mcp_integration = MCPIntegration(registry)

# Register all tools from MCP server
await mcp_integration.register_mcp_tools_async("ws://localhost:8000")

# Tools are automatically wrapped with MCPToolWrapper
```

### Transport Configuration

```python
from fastmcp.client import ClientTransport

# Different transport types
ws_transport = ClientTransport("ws://localhost:8000")
http_transport = ClientTransport("http://localhost:8000")
file_transport = ClientTransport("./mcp_server.py")

wrapper = MCPToolWrapper(file_transport, "local_tool", params=["input"])
```

## Error Handling

The wrapper provides comprehensive error handling:

- **Connection Errors**: Network and transport-related failures
- **Protocol Errors**: MCP specification compliance issues
- **Content Type Errors**: Unsupported content type handling
- **Tool Execution Errors**: Individual tool execution failures

All errors are logged with full stack traces for debugging while preserving the original exception behavior.

## Transport Support

Supports multiple MCP transport mechanisms:

- **WebSocket**: Real-time bidirectional communication
- **HTTP**: REST-based communication
- **File-based**: Local script execution
- **Custom**: User-defined transport implementations

This makes MCPToolWrapper a robust adapter for integrating MCP servers into the ToolRegistry ecosystem.
