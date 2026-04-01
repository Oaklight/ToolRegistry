# MCPToolWrapper

!!! warning "本页尚未翻译"
    本页内容尚未翻译为中文。以下为英文原文，中文翻译将在后续版本中提供。

Wrapper class providing both async and sync versions of MCP (Model Context Protocol) tool calls.

## Overview

`MCPToolWrapper` serves as the specialized wrapper for Model Context Protocol (MCP) servers, providing seamless communication between ToolRegistry and MCP-based tools. It handles the complexities of MCP protocol communication, including various content types, transport management, and error handling.

## Key Features

- **MCP Protocol Integration**: Full support for Model Context Protocol specification
- **Multi-Transport Support**: Handles different transport types (HTTP, WebSocket, file-based)
- **Content Type Handling**: Support for text, image, and embedded resource content
- **Transport Abstraction**: Transparent management of MCP transport connections
- **Error Resilience**: Comprehensive error handling with detailed logging
- **Async/Sync Compatibility**: Both asynchronous and synchronous execution modes

## Architecture

The MCPToolWrapper extends `BaseToolWrapper` with MCP-specific functionality:

### Core Components

1. **Transport Management**: Handles MCP transport lifecycle and communication
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
from toolregistry.mcp.integration import MCPToolWrapper

# Create wrapper for specific MCP tool
wrapper = MCPToolWrapper(
    transport="ws://localhost:8000",
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
from toolregistry.mcp.integration import MCPToolWrapper

# Different transport types (pass URL strings or file paths directly)
wrapper_ws = MCPToolWrapper("ws://localhost:8000", "remote_tool", params=["input"])
wrapper_http = MCPToolWrapper("http://localhost:8000/mcp", "remote_tool", params=["input"])
wrapper_file = MCPToolWrapper("./mcp_server.py", "local_tool", params=["input"])
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
- **HTTP**: Streamable HTTP and SSE-based communication
- **File-based**: Local script execution (`.py`, `.js`)
- **Dict config**: Stdio-based transport via command configuration

This makes MCPToolWrapper a robust adapter for integrating MCP servers into the ToolRegistry ecosystem.
