---
title: 更新日志
summary: ToolRegistry 项目的版本更新历史和变更记录
description: 详细记录了 ToolRegistry 从 0.1.0 版本以来的所有功能更新、修复和改进
keywords: changelog, 更新日志, 版本历史, 变更记录
author: Oaklight
---

# 更新日志

本页面记录了 ToolRegistry 项目自首个发布版本以来的所有重要变更。

## [0.5.0] - 2026-03-10

### 重构

- **MCP 客户端从 fastmcp 解耦**（[#64](../../issues/64)、[#65](../../pull/65)）
	- 使用官方 `mcp` SDK 在 `mcp/client.py` 中创建 `MCPClient` 适配器
	- 从 `integration.py`、`utils.py` 和 `tool_registry.py` 中移除所有 `fastmcp` 导入
	- 将 `[mcp]` 额外依赖从 `fastmcp` 改为 `mcp>=1.0.0`
	- 添加 v1/v2 双版本兼容，支持 camelCase/snake_case 属性
	- 支持全部四种传输方式：stdio、SSE、streamable-http、websocket
	- 添加 `headers` 参数用于 HTTP 认证
	- 添加 25 个覆盖 `MCPClient` 功能的新测试

- **移除 `toolregistry[hub]` 可选附加包**（[#50](../../issues/50)、[#56](../../pull/56)）
	- 从 `pyproject.toml` 的可选依赖中移除 `hub = ['toolregistry-hub>=0.4.14']`
	- 用户现在应直接通过 `pip install toolregistry-hub` 安装 hub 工具
	- 两个包同时安装时 `from toolregistry.hub import ...` 的兼容路径仍可正常使用
	- 相应更新安装文档、hub 集成文档和 README

### 新功能

- **启用/禁用原因追踪**（[#53](../../issues/53)、[#58](../../pull/58)）
	- 添加方法级和命名空间级的禁用，支持原因追踪
	- 新增 `disable(name, reason)`、`enable(name)`、`is_enabled(tool_name)`、`get_disable_reason(tool_name)` 方法
	- `list_tools()` 现在仅返回已启用的工具
	- 新增 `list_all_tools()` 用于管理面板（返回包括已禁用在内的所有工具）
	- `get_tools_json()` 在未指定工具名时自动过滤已禁用工具
	- `execute_tool_calls()` 对已禁用工具返回错误信息而非执行
	- 添加 28 个新测试

- **命名空间与 MRO 支持**（[#51](../../issues/51)、[#52](../../issues/52)、[#57](../../pull/57)）
	- 为 `Tool` 模型添加 `namespace`、`method_name` 字段和 `qualified_name` 属性
	- `_update_sub_registries()` 改用 `namespace` 字段分组，消除 `-`/`_` 歧义
	- 为 `register_from_class()` 和 `register_from_class_async()` 添加 `traverse_mro` 参数
	- 将 `traverse_mro` 默认值改为 `True`，子类方法优先于父类方法

### ⚠️ 破坏性变更

- `register_from_class()` 现在默认 `traverse_mro=True`，继承的公共静态方法和实例方法将自动注册。如需保持旧行为，请显式传入 `traverse_mro=False`

### 维护

- 将 MCP SDK 固定到 `<2.0.0` 以避免 v2 破坏性变更，同时等待官方 MCP SDK v2 支持的开发完成
- 移除未使用的 `beautifulsoup4` 依赖

## [0.4.14] - 2025-08-11

### 新功能

- **类型系统重构**
	- 模块化并扩展类型定义
	- 添加自定义工具调用支持
	- 添加工具调用转换的全面错误处理和验证

- **Hub 模块独立**
	- 将 Hub 模块迁移至外部包（`toolregistry-hub`）
	- 为 `toolregistry.hub` 添加替代导入路径
	- 更新安装文档以包含 Hub 工具说明

### 文档改进

- 重新组织 Hub 文档并添加新 Hub 工具文档
- 添加 0.4.14 版本包拆分说明

## [0.4.13] - 2025-06-20

### 新功能

- **OpenAI Response API 支持**
	- 添加 `ResponseFunctionToolCall` 模型
	- 为 `get_tools_json` 添加 `api_mode` 参数用于 JSON Schema 生成
	- 添加 `recover_tool_message` 函数
	- 为 `result` 字段添加自定义序列化器
	- 添加 `ChatCompletionMessage` 模型

- **Executor 改进**
	- 添加异步函数的同步包装器
	- 添加工具调用管理执行器

- **OpenAPI 增强**
	- 导出 `HttpxClientConfig`
	- 为 httpx 客户端创建添加重载支持

### 重构

- 重构工具调用处理以实现更清晰的架构
- 简化工具参数验证
- 简化 FastMCP 导入和使用
- 统一 API 模式格式

### 修复

- 修复计算器：正确处理不可调用属性
- 修复集成：优雅处理空参数
- 修复工具：解决内部 MCP 服务器检索问题
- 修复执行器：修正函数类型提示
- 修复 toolregistry：处理事件循环关闭问题
- 修复参数模型：修正字段创建逻辑
- 修复 toolregistry：修正客户端配置类型

### 维护

- 将类型检查器从 mypy 更新为 pyright
- 更新依赖版本
- 更新 mcp 依赖版本范围（Closes #36）

### 文档改进

- 添加 OpenAI Chat Completion 和 Response API 集成指南
- 添加 toolregistry 模块文档
- 更新 MCP 传输方式文档

## [0.4.12] - 2025-06-04

### 新功能

- **计算器重构**
	- 从 `Calculator` 中分离 `BaseCalculator`，实现更清晰的架构

- **OpenAPI 集成**
	- 将 OpenAPI 集成重构为模块化结构
	- 添加 FastAPI 作为开发依赖

### 重构

- 重构类工具集成实现
- 重新组织 MCP 集成代码
- 重新组织 LangChain 集成
- 将工具函数移至 native 模块

### 维护

- 废弃带标签的函数
- 更新测试用例的注册表键格式

### 文档改进

- 更新 OpenAPI 集成指南和示例
- 重新生成重组后的 Sphinx 文档

## [0.4.11] - 2025-06-03

### 新功能

- **网络搜索增强**
	- 为 websearch 模块添加 fetch 工具
	- 添加带 GitHub raw 代理支持的屏蔽列表过滤
	- 为移动端用户代理添加 accept 请求头
	- 添加从 Bing 重定向中提取真实 URL

- **搜索结果过滤**（Closes #29）
	- 改进搜索结果过滤和屏蔽列表缓存机制

### 修复

- 修复 websearch_bing：调整分页参数
- 修复 websearch：处理屏蔽列表解析中的域名分隔符

### 文档改进

- 添加 websearch 和 fetch 工具文档
- 添加 websearch 模块文档

## [0.4.10] - 2025-05-23

### 新功能

- **Bing 搜索集成**
	- 为 websearch 模块添加 Bing 搜索功能

- **MCP 传输**
	- 添加 streamable-http 传输模式支持
	- 修复 MCP 集成中的传输类型处理

- **ToolSpec 重构**
	- 使用 `ToolSpec` 简化工具创建流程

### 修复

- 修复 MCP 工具名称规范化导致执行报错的问题（Closes #25）

### 重构

- 集中化 lynx 请求头生成
- 统一请求头变量命名

### 文档改进

- 添加 Read the Docs 配置
- 重构 Hub 和示例文档
- 添加多语言文档支持
- 添加多种示例指南（连续工具调用、Hub 计算器、MCP、OpenAPI、LangChain）

## [0.4.9] - 2025-05-21

### 新功能

- **LangChain 集成**
	- 添加 LangChain 工具注册支持
	- 添加 LangChain 集成模块和 arxiv 示例

- **异步支持**
	- 为方法注册添加 asyncio 支持
	- 使用异步注册逻辑重构 OpenAPI 集成

- **基础工具包装器**
	- 添加 `BaseToolWrapper` 抽象基类
	- 标准化工具包装器继承

### 重构

- 重新组织示例文件结构
- 将 print 语句替换为 logger.error
- 使用 ABC 增强基础工具包装器

### 文档改进

- 添加 LangChain 集成指南
- 更新 README 中的 LangChain 集成文档

## [0.4.8.post1] - 2025-05-13

### 新功能

- **计算器增强**
	- 添加 `function_help` 并扩展 `evaluate` 功能
	- 添加获取静态方法的工具函数

- **示例**
	- 添加 OpenAI 计算器示例

### 文档改进

- 更新计算器工具文档
- 为首页添加 PyPI 版本徽章

## [0.4.8] - 2025-05-11

### 新功能

- **计算器**
	- 为特定函数添加 Python 版本检查

- **OpenAPI**
	- 使用轻量级依赖替换重量级 OpenAPI 依赖
	- 简化规范解析逻辑

### 重构

- 清理导入和类型注解

## [0.4.7] - 2025-05-10

### 新功能

- **Google 搜索工具**
	- 为 websearch hub 添加 Google 搜索功能
	- 添加增强的内容提取方法
	- 添加通用网络搜索抽象类（`WebSearchGeneral`）

- **MCP 传输**
	- 添加多种 MCP 传输模式支持（SSE、stdio、streamable-http）
	- 添加基于 fastmcp 的数学服务器和客户端
	- 添加多样化传输示例

- **类型注解**
	- 为 toolregistry 添加类型提示支持

### 重构

- 从 `mcp` 库迁移至 `fastmcp`
- 简化异常处理和工具注册
- 重新组织 websearch 模块结构

### 文档改进

- 更新传输方式和工具注册表文档
- 添加 websearch 模块文档
- 更新 MCP 集成指南

## [0.4.6.post2] - 2025-04-28

### 修复

- 在 `python>=3.9` 时条件导入 `fake-useragent`（修复 Python 3.8 兼容性问题）
- 解决 websearch 模块中的导入兼容性问题

## [0.4.6.post1] - 2025-04-28

### 新功能

- 添加基于 Google 的 websearch hub 工具
- 使用 `WebSearchGeneral` 抽象类统一 websearch

> **注意**：请使用 0.4.6.post2 版本 —— 此版本在 Python 3.8 上存在依赖问题。

## [0.4.6] - 2025-04-28

### 新功能

- **SearXNG 网络搜索**
	- 添加基于 SearXNG 的 websearch hub 工具

- **类型系统**
	- 使用 Pydantic 在 utils 中复制 OpenAI 类型

> **注意**：请使用 0.4.6.post2 版本 —— 此版本在 Python 3.8 上存在依赖问题。

## [0.4.5] - 2025-04-17

### 新功能

- **并发工具执行**
	- 添加使用 `dill` 序列化的并发工具执行

- **命名空间分隔符**
	- 完善命名空间分隔符配置

## [0.4.4] - 2025-04-16

### 新功能

- **类注册方法升级**
	- 增强基于类的工具注册功能

## [0.4.3] - 2025-04-15

### 新功能

- **计算器增强功能**
	- 添加增强的计算器功能

- **文件操作**
	- 添加文件操作 Hub 工具
	- 完善 FileSystem 工具

## [0.4.2] - 2025-04-14

### 重构

- **命名空间重构和工具 Hub**
	- 重构命名空间处理
	- 引入工具 Hub 模式

## [0.4.1] - 2025-04-12

### 新功能

- **名称规范化**
	- 添加名称规范化以实现一致的工具命名

### 重构

- 更新 README 软链接和 OpenAPI 测试示例

## [0.4.0] - 2025-04-05

### 新功能

- **OpenAPI 支持**
	- 添加从 OpenAPI 规范注册工具的 OpenAPI 集成

### 文档改进

- 增强 toolregistry 的 docstrings
- 添加全面的 API 文档

## [0.3.1] - 2025-04-04

### 新功能

- **统一同步与异步接口**
	- 统一同步和异步模式的可调用接口
	- 完善 MCP 的异步调用机制

### 文档改进

- 添加文档文件和生成脚本

## [0.3.0] - 2025-04-01

### 新功能

- **MCP 工具支持**
	- 添加对 MCP SSE 工具的支持
	- 添加运行工具的异步和同步模式
	- 添加 MCP 工具的结果后处理
	- 增强工具管理能力

### 重构

- 改进工具查找方法
- 移除冗余执行方法
- 简化工具运行方法的结果处理

### 文档改进

- 添加 MCP 集成指南和使用示例
- 更新安装要求中的 MCP 详情

## [0.2.0] - 2025-04-01

### 新功能

- **并行工具执行**
	- 添加工具调用的并行执行

- **项目配置**
	- 从 `setup.py` 迁移至 `pyproject.toml`
	- 添加版本元数据

### 文档改进

- 添加中文 README
- 更新文档中的示例文件路径

## [0.1.0] - 2025-04-01

### 初始发布

- 从 cicada 项目独立出来的初始版本
- 实现用于管理和执行 LLM 工具调用的基础 ToolRegistry
- 核心工具注册和执行框架
- 支持 Python 函数工具

---

## 版本说明

### 语义化版本控制

本项目遵循 [语义化版本控制](https://semver.org/lang/zh-CN/) 规范：

- **主版本号**：不兼容的 API 修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

### 变更类型说明

- **新功能** - 新增功能或特性
- **重构** - 代码重构，不影响功能
- **修复** - 错误修复
- **文档改进** - 文档更新
- **维护** - 维护性更新
- **构建** - 构建系统变更

### 获取更新

要获取最新版本，请使用：

```bash
pip install --upgrade toolregistry
```

### 反馈和建议

如果您发现任何问题或有改进建议，请在我们的 [GitHub 仓库](https://github.com/Oaklight/ToolRegistry) 提交 Issue。
