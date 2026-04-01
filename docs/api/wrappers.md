# 工具包装器

工具包装器是适配器类，用于在外部工具格式与 ToolRegistry 的标准化接口之间进行转换。每个包装器都实现了基类中的 `call_sync()` 和 `call_async()` 方法。

## 可用包装器

| 包装器 | 来源 | 参考 |
|---------|--------|-----------|
| [BaseToolWrapper](wrappers/basetoolwrapper.md) | 所有包装器的抽象基类 | 定义 `call_sync()` / `call_async()` 契约 |
| [MCPToolWrapper](wrappers/mcp.md) | MCP 服务器 | 多传输方式、多内容类型支持 |
| [OpenAPIToolWrapper](wrappers/openapi.md) | REST API | 支持 GET/POST/PUT/DELETE 的 HTTP 客户端 |
| [LangChainToolWrapper](wrappers/langchain.md) | LangChain 工具 | 将 `_run()` / `_arun()` 桥接到 ToolRegistry |

## 执行模型

所有包装器支持自动执行模式检测：

```python
# Sync context → calls call_sync()
result = wrapper(a=5, b=3)

# Async context → calls call_async()
result = await wrapper(a=5, b=3)
```

## 参见

- [集成模块](integrations.md) — 创建和注册包装工具的集成类
- [BaseToolWrapper API](wrappers/basetoolwrapper.md) — 自定义包装器的子类化指南
