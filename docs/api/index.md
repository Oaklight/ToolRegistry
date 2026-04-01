# API 参考

ToolRegistry 中所有类和方法的全面 API 文档，从源代码自动生成。

## 核心类

基础类和基本组件：

- [**ToolRegistry**](core/toolregistry.md) — 工具管理的中央协调器
- [**Tool**](core/tool.md) — 包含元数据和执行逻辑的单个工具
- [**Executor**](core/executor.md) — 可插拔的执行后端（线程/进程）
- [**Events**](events.md) — 变更事件类型和回调机制
- [**Permissions**](permissions.md) — 基于规则的授权框架

参见 [核心类概览](core.md) 了解架构图。

## 集成模块

框架和协议兼容性，用于工具注册：

- [**OpenAPI**](integrations/openapi.md) — 从 OpenAPI 规范生成 REST API 工具
- [**MCP**](integrations/mcp.md) — 模型上下文协议服务器通信
- [**LangChain**](integrations/langchain.md) — LangChain BaseTool 互操作性
- [**Native**](integrations/native.md) — Python 类方法注册

参见 [集成模块概览](integrations.md) 了解通用模式。

## 工具包装器

不同工具类型的适配器类：

- [**BaseToolWrapper**](wrappers/basetoolwrapper.md) — 抽象基类
- [**MCPToolWrapper**](wrappers/mcp.md) — MCP 服务器工具包装器
- [**OpenAPIToolWrapper**](wrappers/openapi.md) — OpenAPI/REST 工具包装器
- [**LangChainToolWrapper**](wrappers/langchain.md) — LangChain 工具包装器

参见 [工具包装器概览](wrappers.md) 了解执行模型。

## 辅助类

支持工具：

- [**参数模型与工具函数**](helpers.md) — 参数验证、工具名规范化、HTTP 客户端配置

## 类型定义

LLM 供应商兼容性类型：

- [**类型**](types.md) — 通用、OpenAI、Anthropic 和 Gemini 类型定义

## 完整模块概览

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
