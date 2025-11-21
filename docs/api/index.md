# API Reference

This section provides comprehensive API documentation for all classes and methods in ToolRegistry, automatically generated from the source code.

## Overview

The ToolRegistry library consists of several main components:

- **Core Classes**: Fundamental classes like `ToolRegistry`, `Tool`, and `BaseToolWrapper`
- **Tool Wrappers**: Specialized wrappers for different tool types (MCP, OpenAPI, LangChain)
- **Modules and Functions**: Utility modules and helper functions
- **Integration Modules**: Compatibility modules for various frameworks
- **Type Definitions**: Type definitions for LLM provider compatibility

## Core Classes

Fundamental classes and base components:

- [`ToolRegistry`](core.md#toolregistry) - The central registry class
- [`Tool`](core.md#tool) - Individual tool representation
- [`BaseToolWrapper`](core.md#basetoolwrapper) - Base wrapper class

## Tool Wrappers

Specialized wrapper classes for different tool types:

- [`MCPToolWrapper`](wrappers.md#mcp-tool-wrapper) - MCP server tool wrapper
- [`OpenAPIToolWrapper`](wrappers.md#openapi-tool-wrapper) - OpenAPI tool wrapper
- [`LangChainToolWrapper`](wrappers.md#langchain-tool-wrapper) - LangChain tool wrapper

## Modules and Functions

Utility modules and helper functions:

- [`executor`](modules.md#executor-module) - Tool execution engine
- [`parameter_models`](modules.md#parameter-models) - Parameter validation
- [`utils`](modules.md#utilities) - Utility functions

## Integration Modules

Framework and protocol compatibility:

- [`MCP Integration`](integrations.md#mcp-integration) - Model Context Protocol support
- [`OpenAPI Integration`](integrations.md#openapi-integration) - OpenAPI/Swagger support
- [`LangChain Integration`](integrations.md#langchain-integration) - LangChain compatibility
- [`Native Integration`](integrations.md#native-integration) - Direct Python integration

## Type Definitions

Type definitions for LLM provider compatibility:

- [`Common Types`](types.md#common-types) - Universal type definitions
- [`OpenAI Types`](types.md#openai-types) - OpenAI API compatibility
- [`Anthropic Types`](types.md#anthropic-types) - Anthropic API compatibility
- [`Gemini Types`](types.md#gemini-types) - Google Gemini API compatibility

## Complete Module Overview

For a complete overview with all classes and functions:

::: toolregistry
options:
show_source: false
show_root_heading: true
show_root_toc_entry: true
members: - ToolRegistry - Tool - executor - parameter_models - utils - hub - mcp - openapi - langchain - native - types
