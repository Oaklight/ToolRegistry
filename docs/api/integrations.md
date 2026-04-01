# Integration Modules

!!! warning "本页尚未翻译"
    本页内容尚未翻译为中文。以下为英文原文，中文翻译将在后续版本中提供。

Integration modules provide compatibility with various frameworks and protocols, enabling tool registration from external sources.

## Available Integrations

| Module | Main Class | Wrapper | Reference |
|--------|-----------|---------|-----------|
| [OpenAPI](integrations/openapi.md) | `OpenAPIIntegration` | `OpenAPIToolWrapper` | REST API tool generation from OpenAPI specs |
| [MCP](integrations/mcp.md) | `MCPIntegration` | `MCPToolWrapper` | Model Context Protocol server communication |
| [LangChain](integrations/langchain.md) | `LangChainIntegration` | `LangChainToolWrapper` | LangChain BaseTool interoperability |
| [Native](integrations/native.md) | `ClassToolIntegration` | — | Python class method registration |

## Common Patterns

All integrations share these patterns:

- **Wrapper + Integration classes**: Wrappers handle execution; Integration classes orchestrate registration
- **Async/sync support**: All integrations support both `register_from_*()` and `register_from_*_async()` methods
- **Namespace support**: `False` (no prefix), `True` (auto-generated), or `str` (custom namespace)
- **Error preservation**: Original framework exceptions are preserved with additional context

## See Also

- [Tool Wrappers](wrappers.md) — Detailed wrapper class documentation
- [Usage: Integrations](../usage/integrations/class.md) — Integration usage guides
