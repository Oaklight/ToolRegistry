# API 参考

本节提供 ToolRegistry 中所有类和方法的全面 API 文档，从源代码自动生成。

## 概览

ToolRegistry 库由几个主要组件组成：

- **核心类**：基础类如 `ToolRegistry`、`Tool` 和 `BaseToolWrapper`
- **工具包装器**：不同工具类型的专用包装器（MCP、OpenAPI、LangChain）
- **模块和函数**：实用模块和辅助函数
- **集成模块**：各种框架的兼容性模块
- **类型定义**：LLM 提供者兼容性的类型定义

## 核心类

基础类和基本组件：

- [`ToolRegistry`](core.md#toolregistry) - 中央注册表类
- [`Tool`](core.md#tool) - 单个工具表示
- [`BaseToolWrapper`](core.md#basetoolwrapper) - 基础包装器类

## 工具包装器

不同工具类型的专用包装器类：

- [`MCPToolWrapper`](wrappers.md#mcp-tool-wrapper) - MCP 服务器工具包装器
- [`OpenAPIToolWrapper`](wrappers.md#openapi-tool-wrapper) - OpenAPI 工具包装器
- [`LangChainToolWrapper`](wrappers.md#langchain-tool-wrapper) - LangChain 工具包装器

## 模块和函数

实用模块和辅助函数：

- [`executor`](modules.md#executor-module) - 工具执行引擎
- [`parameter_models`](modules.md#parameter-models) - 参数验证
- [`utils`](modules.md#utilities) - 实用函数

## 集成模块

框架和协议兼容性：

- [`MCP 集成`](integrations.md#mcp-integration) - 模型上下文协议支持
- [`OpenAPI 集成`](integrations.md#openapi-integration) - OpenAPI/Swagger 支持
- [`LangChain 集成`](integrations.md#langchain-integration) - LangChain 兼容性
- [`原生集成`](integrations.md#native-integration) - 直接 Python 集成

## 类型定义

LLM 提供者兼容性的类型定义：

- [`通用类型`](types.md#common-types) - 通用类型定义
- [`OpenAI 类型`](types.md#openai-types) - OpenAI API 兼容性
- [`Anthropic 类型`](types.md#anthropic-types) - Anthropic API 兼容性
- [`Gemini 类型`](types.md#gemini-types) - Google Gemini API 兼容性

## 完整模块概览

有关所有类和函数的完整概览：

::: toolregistry
options:
show_source: false
show_root_heading: true
show_root_toc_entry: true
members: - ToolRegistry - Tool - executor - parameter_models - utils - hub - mcp - openapi - langchain - native - types
