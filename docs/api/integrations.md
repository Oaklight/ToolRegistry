# 集成模块

集成模块提供与各种框架和协议的兼容性，支持从外部来源注册工具。

## 可用集成

| 模块 | 主类 | 包装器 | 参考 |
|--------|-----------|---------|-----------|
| [OpenAPI](integrations/openapi.md) | `OpenAPIIntegration` | `OpenAPIToolWrapper` | 从 OpenAPI 规范生成 REST API 工具 |
| [MCP](integrations/mcp.md) | `MCPIntegration` | `MCPToolWrapper` | Model Context Protocol 服务器通信 |
| [LangChain](integrations/langchain.md) | `LangChainIntegration` | `LangChainToolWrapper` | LangChain BaseTool 互操作 |
| [Native](integrations/native.md) | `ClassToolIntegration` | — | Python 类方法注册 |

## 通用模式

所有集成共享以下模式：

- **Wrapper + Integration 类**：Wrapper 处理执行；Integration 类编排注册流程
- **异步/同步支持**：所有集成均支持 `register_from_*()` 和 `register_from_*_async()` 方法
- **命名空间支持**：`False`（无前缀）、`True`（自动生成）或 `str`（自定义命名空间）
- **错误保留**：保留原始框架异常并附加额外上下文

## 参见

- [工具包装器](wrappers.md) — 包装器类的详细文档
- [使用指南：集成](../usage/integrations/class.md) — 集成使用指南
