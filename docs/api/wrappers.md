# Tool Wrappers

!!! warning "本页尚未翻译"
    本页内容尚未翻译为中文。以下为英文原文，中文翻译将在后续版本中提供。

Tool wrappers are adapter classes that translate between external tool formats and the ToolRegistry's standardized interface. Each wrapper implements `call_sync()` and `call_async()` from the base class.

## Available Wrappers

| Wrapper | Source | Reference |
|---------|--------|-----------|
| [BaseToolWrapper](wrappers/basetoolwrapper.md) | Abstract base class for all wrappers | Defines `call_sync()` / `call_async()` contract |
| [MCPToolWrapper](wrappers/mcp.md) | MCP servers | Multi-transport, multi-content-type support |
| [OpenAPIToolWrapper](wrappers/openapi.md) | REST APIs | HTTP client with GET/POST/PUT/DELETE |
| [LangChainToolWrapper](wrappers/langchain.md) | LangChain tools | Bridges `_run()` / `_arun()` to ToolRegistry |

## Execution Model

All wrappers support automatic execution mode detection:

```python
# Sync context → calls call_sync()
result = wrapper(a=5, b=3)

# Async context → calls call_async()
result = await wrapper(a=5, b=3)
```

## See Also

- [Integration Modules](integrations.md) — Integration classes that create and register wrapped tools
- [BaseToolWrapper API](wrappers/basetoolwrapper.md) — Subclassing guide for custom wrappers
