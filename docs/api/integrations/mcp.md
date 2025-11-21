# MCP Integration

This section documents the Model Context Protocol (MCP) integration capabilities of the ToolRegistry library.

## Architecture Overview

The MCP integration enables seamless communication with Model Context Protocol servers, allowing LLM applications to utilize tools provided by external MCP servers. The architecture follows a client-server communication model:

### Core Components

1. **MCPToolWrapper**: A wrapper class that provides both synchronous and asynchronous communication with MCP servers

   - Handles tool execution via MCP protocol
   - Supports various content types (text, image, embedded resources)
   - Manages client transport and communication lifecycle

2. **MCPTool**: A tool class that wraps MCP tool specifications

   - Preserves original tool metadata and descriptions
   - Converts MCP schemas to ToolRegistry format
   - Supports namespace organization

3. **MCPIntegration**: The main integration class that orchestrates server communication
   - Manages client connections to MCP servers
   - Discovers available tools from servers
   - Handles transport abstraction for different connection types

### Communication Architecture

- **Transport Layer**: Supports multiple transport types (HTTP, WebSocket, file-based)
- **Protocol Layer**: Implements MCP specification for tool discovery and execution
- **Content Processing**: Handles multiple content types with post-processing

### Key Features

- Support for various transport types (URL, file paths, server instances)
- Automatic tool discovery from MCP servers
- Multi-format content support (text, images, embedded resources)
- Namespace management for tool organization
- Robust error handling with detailed logging
- Both synchronous and asynchronous operation modes

### Transport Support

The integration supports multiple transport mechanisms:

- HTTP/HTTPS endpoints
- WebSocket connections
- Local file paths (Python scripts, JavaScript files)
- Existing ClientTransport instances
- FastMCP server instances

## API Reference

### MCPToolWrapper

Wrapper class providing both async and sync versions of MCP tool calls.

::: toolregistry.mcp.integration.MCPToolWrapper
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### MCPTool

Wrapper class for MCP tools that preserves original function metadata.

::: toolregistry.mcp.integration.MCPTool
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### MCPIntegration

Handles integration with MCP server for tool registration.

::: toolregistry.mcp.integration.MCPIntegration
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Module Utilities

### MCP Utils

Utility functions for MCP processing and transport management.

::: toolregistry.mcp.utils
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### MCP Module

The main MCP integration module.

::: toolregistry.mcp
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true
