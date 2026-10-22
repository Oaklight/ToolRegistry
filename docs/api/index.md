# API Reference

Comprehensive API documentation for all classes and methods in ToolRegistry, automatically generated from the source code.

## Core Classes

Fundamental classes and base components:

- [**ToolRegistry**](core/toolregistry.md) — Central orchestrator for tool management
- [**Tool**](core/tool.md) — Individual tool with metadata and execution logic
- [**Executor**](core/executor.md) — Pluggable execution backends (thread/process)
- [**Events**](events.md) — Change event types and callback mechanism
- [**Permissions**](permissions.md) — Rule-based authorization framework

See [Core Classes Overview](core.md) for architecture diagram.

## Integration Modules

Framework and protocol compatibility for tool registration:

- [**OpenAPI**](integrations/openapi.md) — REST API tool generation from OpenAPI specs
- [**MCP**](integrations/mcp.md) — Model Context Protocol server communication
- [**LangChain**](integrations/langchain.md) — LangChain BaseTool interoperability
- [**Native**](integrations/native.md) — Python class method registration

See [Integration Modules Overview](integrations.md) for common patterns.

## Tool Wrappers

Adapter classes for different tool types:

- [**BaseToolWrapper**](wrappers/basetoolwrapper.md) — Abstract base class
- [**MCPToolWrapper**](wrappers/mcp.md) — MCP server tool wrapper
- [**OpenAPIToolWrapper**](wrappers/openapi.md) — OpenAPI/REST tool wrapper
- [**LangChainToolWrapper**](wrappers/langchain.md) — LangChain tool wrapper

See [Tool Wrappers Overview](wrappers.md) for execution model.

## Helper Classes

Supporting utilities:

- [**Parameter Models & Utilities**](helpers.md) — Parameter validation, tool name normalization, HTTP client configuration

## Validation Errors

Tools validate their arguments before running. The exceptions are importable from the
package root, so a caller can map them to its own error format without touching a
private module:

```python
from toolregistry import ErrorDetail, SchemaValidationError, ValidationError

try:
    tool.validate_parameters(arguments)
except ValidationError as exc:
    for detail in exc.errors:          # ErrorDetail(path, expected, actual, message)
        print(detail.path, detail.message)
```

- `ValidationError` / `ErrorDetail` — raised by `Tool.validate_parameters()`, which
  validates signature-derived tools against their parameter model.
- `SchemaValidationError` / `SchemaErrorDetail` — raised when data is validated
  against a raw JSON Schema, as proxy tools (MCP / OpenAPI / LangChain) are.

Both `except` the same classes the library raises; the names are re-exports, not
wrappers.

## Type Definitions

LLM API format compatibility types:

- [**Types**](types.md) — Common, OpenAI, Anthropic, and Gemini type definitions

## Complete Module Overview

::: toolregistry
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: true
        members:
            - ToolRegistry
            - Tool
            - executor
            - parameter_models
            - utils
            - hub
            - mcp
            - openapi
            - langchain
            - native
            - types
            - errors
