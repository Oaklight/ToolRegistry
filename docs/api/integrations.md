# Integration Modules

This section documents the integration modules that provide compatibility with various frameworks and protocols.

## Available Integrations

The ToolRegistry library provides several integration modules to work with different frameworks and protocols:

### OpenAPI Integration

Integration with OpenAPI/Swagger specifications for automatic REST API tool generation.

- **Overview**: [OpenAPI Integration](integrations/openapi.md)
- **Tool Wrapper**: `OpenAPIToolWrapper`
- **Main Class**: `OpenAPIIntegration`
- **Features**: Automatic endpoint discovery, parameter schema extraction, async/sync support

### MCP Integration

Support for Model Context Protocol (MCP) servers for tool discovery and execution.

- **Overview**: [MCP Integration](integrations/mcp.md)
- **Tool Wrapper**: `MCPToolWrapper`
- **Main Class**: `MCPIntegration`
- **Features**: Multi-transport support, content type handling, server discovery

### LangChain Integration

Compatibility with LangChain tools for seamless interoperability.

- **Overview**: [LangChain Integration](integrations/langchain.md)
- **Tool Wrapper**: `LangChainToolWrapper`
- **Main Class**: `LangChainIntegration`
- **Features**: Schema conversion, async/sync execution, error preservation

### Native Integration

Direct integration with Python classes and functions.

- **Overview**: [Native Integration](integrations/native.md)
- **Integration Class**: `ClassToolIntegration`
- **Features**: Automatic method discovery, smart instantiation, namespace management

## Integration Patterns

### Common Patterns

All integrations follow these common patterns:

1. **Wrapper Classes**: Each integration provides a wrapper class that extends `BaseToolWrapper`
2. **Tool Classes**: Specialized tool classes that preserve framework-specific metadata
3. **Integration Classes**: Main classes that orchestrate the registration process
4. **Async/Sync Support**: All integrations support both synchronous and asynchronous operation modes

### Namespace Support

All integrations support namespace organization:

- `False`: No namespace prefix
- `True`: Auto-generated namespace from framework metadata
- `str`: Custom namespace string

### Error Handling

- **Framework Preservation**: Original framework exceptions are preserved
- **Context Enhancement**: Additional context is added to error messages
- **Logging Integration**: Detailed logging for debugging and monitoring
