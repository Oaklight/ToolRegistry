---
title: 更新日志
summary: ToolRegistry 项目的版本更新历史和变更记录
description: 详细记录了 ToolRegistry 从 0.1.0 版本以来的所有功能更新、修复和改进
keywords: changelog, 更新日志, 版本历史, 变更记录
author: Oaklight
---

# 更新日志

本页面记录了 ToolRegistry 项目自首个发布版本以来的所有重要变更。

## Unreleased

### 新特性

- **管理面板增强**（[#133](../../pull/133)）
    - 丰富工具 API 响应，包含完整元数据：`ToolTag` 标签、`ToolMetadata` 字段（`is_async`、`timeout`、`locality`、`think_augment`、`defer` 等）以及权限评估结果
    - 新增 `GET /api/tools/{name}/permissions` 端点，支持单个工具的权限策略评估
    - 在 Web UI 中新增工具详情弹窗，支持标签页切换（Schema、Metadata、Permissions）
    - 在工具行中添加系统 `ToolTag` 标签（彩色编码）和自定义标签
    - 将单字母元数据图标（`T`、`D`）替换为完整词标签（`think`、`defer`、`async`、`local`/`remote`）
    - 在工具面板中添加搜索和基于标签的过滤功能
    - 改进移动端响应式布局，支持水平滚动，小视口下隐藏原因列
    - 新增 7 个测试覆盖丰富 API 和权限端点

- **think_augment 和 defer 运行时控制**（[#134](../../issues/134)、[#135](../../pull/135)）
    - 为 `ToolRegistry` 新增 `update_tool_metadata(tool_name, **kwargs)` 和 `update_namespace_metadata(namespace, **kwargs)` 方法，支持运行时修改 `think_augment` 和 `defer` 字段
    - 白名单机制：仅允许运行时修改 `think_augment` 和 `defer`（防止对执行关键字段的不安全修改）
    - 新增 `PATCH /api/tools/{name}/metadata` 和 `PATCH /api/namespaces/{ns}/metadata` REST API 端点
    - 在 Web UI 中为 `think_augment` 和 `defer` 添加独立列的交互式复选框，支持工具级别和命名空间级别
    - 原生声明了 `thought` 参数的工具，Think 复选框灰显；在 `get_tools_status()` API 中暴露 `has_native_thought` 字段
    - 命名空间级别的复选框应用于命名空间内的所有工具
    - 在 `ChangeEventType` 枚举中新增 `METADATA_UPDATE` 事件类型
    - 新增 7 个测试覆盖元数据更新端点

- **管理面板国际化（i18n）**（[#137](../../pull/137)）
    - 为管理面板 Web UI 添加双语支持（英文/中文）
    - 标题栏中的语言切换下拉框，通过 `localStorage` 持久化偏好
    - 所有静态文本使用 `data-i18n` 属性；动态文本使用 `t(key, params)` 翻译函数
    - 覆盖所有标签页、表头、按钮、过滤器、提示消息、弹窗对话框和空状态
    - 即时语言切换，自动重新渲染当前活动标签页
    - 连接状态简化为圆点指示器，悬停显示提示文字

### 重构

- **移除 httpx 核心依赖** ([#139](../../pull/139))
    - 使用零依赖的内置 HTTP 客户端替代 `httpx`，用于核心 OpenAPI 功能
    - `HttpxClientConfig` 重命名为 `HttpClientConfig`（旧名保留为弃用别名，使用时会发出 `DeprecationWarning`）
    - 将 `httpx` 从核心 `dependencies` 移至 `[mcp]` 可选依赖（MCP 集成仍需要 httpx）
    - 公开 API 行为不变——`HttpClientConfig` 接受相同的构造函数参数

- **管理面板异步化迁移**（[#136](../../pull/136)）
    - 将管理面板从标准库 `http.server` 迁移至 zerodep 的异步 `httpserver` 模块（通过 `zerodep add httpserver` 引入）
    - 将 `BaseHTTPRequestHandler` 替换为装饰器路由（`@app.get`、`@app.post`、`@app.patch`、`@app.delete`）
    - 通过 `before_request`/`after_request` 中间件统一处理认证和 CORS
    - 在后台线程中运行 `asyncio.new_event_loop()` 替代 `HTTPServer.serve_forever()`
    - 移除 `AdminRequestHandler` 类（内部实现细节，替换为 `setup_routes()`）
    - 简化 `TokenAuth` 为纯令牌管理 — HTTP 认证逻辑移至中间件
    - 在 `pyproject.toml` 中将 `_vendor/` 排除出 ruff、ty 和 complexipy 检查

## [0.8.0] - 2026-05-02

### 新特性

- **声明式工具配置加载器**（[#120](../../issues/120)、[#122](../../pull/122)）
    - 新增 `toolregistry.config` 模块，支持将 JSONC/YAML 配置文件解析为类型化的冻结 dataclass
    - 支持三种工具源类型：`python`（类/模块）、`mcp`（stdio/sse/streamable-http）、`openapi`（含认证）
    - 将 `zerodep/jsonc` 和 `zerodep/yaml` 作为 vendor 模块放入 `_vendor/` 包，保持零外部依赖
    - `transport: "http"` 作为 `"streamable-http"` 的别名
    - 向后兼容旧版 `{"module": "x", "class": "Y"}` 配置格式
    - 支持 denylist/allowlist 模式、按源启用/禁用以及 `token_env` 环境变量解析

### 重构

- **集成包结构重组**
    - 将 `mcp/`、`openapi/`、`langchain/`、`native/` 集成包移至新的 `integrations/` 父包下
    - 新的规范导入路径：`toolregistry.integrations.mcp`、`toolregistry.integrations.openapi`、`toolregistry.integrations.langchain`、`toolregistry.integrations.native`
    - 旧导入路径（`toolregistry.mcp`、`toolregistry.openapi` 等）保留为弃用兼容层，会发出 `DeprecationWarning`；这些兼容层将在未来版本中移除
    - 公开的 `ToolRegistry` API 方法（`register_from_mcp()`、`register_from_openapi()` 等）保持不变

- **整合内部模块**
    - 将 mixin 模块整合至 `_mixins/` 包
    - 将零依赖 vendor 模块整合至 `_vendor/` 包
    - 为 llm-rosetta ToolOps 使用子包级导入

### 修复

- **改进带必需构造参数类的错误消息**（[#127](../../issues/127)）
    - 当 `register_from_class()` 用于构造函数需要参数的类时，提供更清晰的错误消息

### 维护

- 将 `llm-rosetta` 最低版本提升至 `>=0.5.1,<0.6.0`

## [0.7.0] - 2026-04-06

### 新特性

- **Anthropic 与 Gemini 模式格式支持**（[#55](../../issues/55)、[#88](../../pull/88)）
    - 为 `get_schemas()` 和 `get_json_schema()` 添加 `"anthropic"` 和 `"gemini"` 作为有效的 `api_format` 值
    - 所有模式转换由 [llm-rosetta](https://pypi.org/project/llm-rosetta/) 驱动，同时清理各格式不支持的 JSON Schema 关键字
    - 添加 `llm-rosetta>=0.2.6` 作为核心依赖
    - 在 `ToolCall.from_tool_call()` 中支持解析 Anthropic `tool_use` 块和 Gemini `functionCall` 部分
    - 为 `build_assistant_message()` 和 `build_tool_response()` 添加 `"anthropic"` 和 `"gemini"` 格式支持

- **权限系统**（[#79](../../issues/79)、[#80](../../issues/80)、[#81](../../issues/81)、[#82](../../issues/82)）
    - **ToolTag 与 ToolMetadata**（[#80](../../issues/80)、[#84](../../pull/84)）：添加 `ToolTag` 枚举（READ_ONLY、DESTRUCTIVE、NETWORK、FILE_SYSTEM、SLOW、PRIVILEGED）和 `ToolMetadata` 模型，包含执行提示（`is_async`、`is_concurrency_safe`、`timeout`）和分类标签
    - **权限处理器协议**（[#81](../../issues/81)、[#85](../../pull/85)）：添加 `PermissionHandler` 和 `AsyncPermissionHandler` 运行时可检查协议用于工具授权；添加 `PermissionRequest` 和 `PermissionResult` 类型；在 ToolRegistry 上添加 `set_permission_handler()`、`get_permission_handler()`、`remove_permission_handler()` 方法
    - **权限规则引擎**（[#82](../../issues/82)、[#86](../../pull/86)）：添加 `PermissionRule` 和 `PermissionPolicy` 模型，采用首次匹配生效评估；添加 `set_permission_policy()`、`get_permission_policy()`、`remove_permission_policy()` 方法；添加五条内置规则（`ALLOW_READONLY`、`ASK_DESTRUCTIVE`、`DENY_PRIVILEGED`、`ASK_NETWORK`、`ASK_FILE_SYSTEM`）；权限检查集成到 `execute_tool_calls()` 中
    - 在回调机制中添加 `PERMISSION_DENIED` 和 `PERMISSION_ASKED` 事件类型

- **ToolMetadata Locality 字段**（[#89](../../issues/89)）
    - 为 `ToolMetadata` 添加 `locality` 字段，可选值为 `"local"`、`"remote"` 或 `"any"`（默认）
    - 支持按执行位置分类工具，便于过滤和调度

- **基于标签的过滤与稳定排序**（[#83](../../issues/83)）
    - 为 `get_schemas()` 添加 `tags`、`exclude_tags` 和 `sort` 参数
    - 支持 prompt 级工具过滤和确定性排序，减少 token 浪费，提高大规模工具池的 prompt 缓存命中率

- **MCP 和 OpenAPI 持久连接**（[#90](../../issues/90)）
    - MCP 集成现通过 `MCPConnectionManager` 在工具调用间保持持久连接
    - OpenAPI 集成复用 `httpx` 客户端会话实现连接池
    - 新增 `ToolRegistry.close()` / `close_async()` 方法用于显式资源清理
    - 支持上下文管理器：`with ToolRegistry() as reg:` 和 `async with ToolRegistry() as reg:`

- **ToolDiscoveryTool 渐进式工具披露**（[#108](../../pull/108)、[#114](../../pull/114)、[#118](../../pull/118)）
    - 新增 `ToolDiscoveryTool` 类，支持双模式发现：精确名称匹配（返回完整 schema）和 BM25F 模糊搜索
    - 内置 zerodep `SparseIndex` 作为 `_sparse_search.py`（零外部依赖）
    - 新增 `ToolMetadata.defer` 字段，标记工具为延迟加载（从初始提示中排除）
    - 新增 `ToolMetadata.search_hint` 字段，支持自由格式的搜索关键词和同义词
    - 索引工具名称、描述、标签、参数名和 search_hint，支持可配置字段权重
    - 新增 `enable_tool_discovery()` / `disable_tool_discovery()`，将 `discover_tools` 注册为 registry 中的一等可调用工具
    - 新增 `get_deferred_summaries()`，获取延迟工具的轻量摘要（名称 + 首句描述），用于注入 system prompt
    - 为 `get_schemas()` 添加 `include_deferred` 参数 — 设为 `False` 可从初始 schema 中排除延迟工具
    - 延迟工具的发现结果包含完整的工具 `schema`，使 LLM 发现后可立即调用
    - 通过 ChangeCallback 在工具注册或注销时自动重建发现索引
    - 新增 `ToolRegistry(tool_discovery=True)` 构造函数参数提供便捷启用方式

- **思维增强函数调用**（[#49](../../pull/49)）
    - 在工具的参数 schema 中注入 `thought` 字符串属性，让 LLM 在调用工具时可以包含链式推理
    - **默认关闭** — 通过 `ToolRegistry(think_augment=True)` 全局启用，或在运行时使用 `enable_think_augment()` / `disable_think_augment()` 切换
    - 支持单个工具覆盖：`ToolMetadata.think_augment`（`None`=跟随注册表、`True`=强制开启、`False`=强制关闭）
    - 该属性在执行前自动剥离
    - 函数原生的 `thought` 参数会被保留（不会被覆盖）
    - 覆盖所有集成路径（MCP、OpenAPI、LangChain、原生）
    - 参考文献：[arXiv:2601.18282](https://arxiv.org/abs/2601.18282)

- **结果大小管理**
    - 新增 `ToolMetadata.max_result_size` 和 `ToolRegistry(default_max_result_size=...)` 用于自动结果截断
    - 两种策略：`HEAD`（保留前 N 个字符）和 `HEAD_TAIL`（保留首尾部分，默认）
    - 截断前完整结果自动持久化到临时文件
    - 新增 `truncate_result()` 函数和 `TruncatedResult` 数据类供编程使用

### 修复

- **Gemini 工具调用 ID 与名称解析**
    - 修复 `build_tool_call_messages` 中的 ID 对齐问题：按位置将 `tool_responses`（由 `execute_tool_calls` 生成）的 ID 映射到转换后的 `ToolCall` 对象上，确保 assistant 和 tool 消息引用相同的 ID
    - 将 `tool_calls` 传递给 `build_tool_response` 以解析 Gemini `functionResponse.name`
    - 此前 Gemini `functionResponse.name` 显示随机 UUID 而非函数名，原因是 `convert_tool_calls()` 被独立调用两次，每次生成不同的 ID

### 重构

- **可插拔 Executor 后端架构**（[#78](../../issues/78)）
    - 将单体 `Executor` 类替换为可插拔的 `executor/` 包
    - 新增 `ExecutionBackend` Protocol 和 `ExecutionHandle` ABC，实现后端可扩展性
    - `ThreadBackend`：线程池执行器，支持通过 `ExecutionContext` 进行协作式取消
    - `ProcessPoolBackend`：进程池执行器，使用 cloudpickle 序列化
    - 在后端层面强制执行 `ToolMetadata.timeout`
    - `ToolMetadata.is_concurrency_safe` 控制顺序执行与并行批处理
    - 工具函数可接受 `_ctx: ExecutionContext` 参数实现协作式取消和进度报告

- **基于 Mixin 的 ToolRegistry 架构**（[#94](../../issues/94)）
    - 将 `tool_registry.py`（1459 行）拆分为 7 个专注的 mixin 类（剩余 454 行）
    - Mixin：`ChangeCallbackMixin`、`NamespaceMixin`、`EnableDisableMixin`、`RegistrationMixin`、`PermissionsMixin`、`ExecutionLoggingMixin`、`AdminMixin`
    - 公开 API 不变；通过 MRO 链实现协作式 `__init__`

- **公开 API 重命名**（[#107](../../issues/107)）
    - `get_tools_json()` → `get_schemas()`（`ToolRegistry` 方法）
    - `recover_tool_call_assistant_message()` → `build_tool_call_messages()`（`ToolRegistry` 方法）
    - `recover_assistant_message()` → `build_assistant_message()`（模块级函数）
    - `recover_tool_message()` → `build_tool_response()`（模块级函数）
    - 所有 `register_from_*` 方法中的 `with_namespace` 参数重命名为 `namespace`（旧名称仍可使用，触发弃用警告）
    - `set_execution_mode()` 重命名为 `set_default_execution_mode()`（旧名称已弃用）
    - `list_all_tools()` 合并至 `list_tools(include_disabled=True)`（旧名称已弃用）
    - 新增 `"openai-chat"` 作为规范 API 格式名称；弃用 `"openai"` 和 `"openai-chatcompletion"`
    - 所有旧名称保留为弃用别名，使用时会触发 `DeprecationWarning`

## [0.6.1] - 2026-03-22

### 修复

- **修复 `**kwargs` 泄漏到工具 JSON Schema**：`_generate_parameters_model()` 现在会跳过 `VAR_POSITIONAL`（`*args`）和 `VAR_KEYWORD`（`**kwargs`）参数，防止它们作为必填字段出现在生成的 schema 中。修复了使用 `**kwargs` 的工具函数在 MCP 调用时出现校验错误的问题。

### 维护

- 将 `pyproject.toml` 切换为动态版本（从 `toolregistry.__version__` 读取），与 toolregistry-server 和 toolregistry-hub 保持一致。

## [0.6.0] - 2026-03-18

### ⚠️ 破坏性变更

- **升级最低 Python 版本至 3.10**（[#74](../../issues/74)）
	- 将 `requires-python` 从 `>=3.8` 更新为 `>=3.10`
	- 不再支持 Python 3.8 和 3.9
	- 与 Python 3.9 EOL 和 MCP SDK 要求保持一致

### 新特性

- **管理面板**（Phase 7）
	- 内置的 ToolRegistry Web 管理界面
	- 执行日志，支持环形缓冲区存储
	- 工具和命名空间管理的 REST API（12 个端点）
	- Anthropic 风格的极简 Web UI 设计
	- 基于令牌的认证，支持远程访问
	- 状态导出/导入功能
	- 新增方法：`enable_admin()`、`disable_admin()`、`get_admin_info()`
	- 新增方法：`enable_logging()`、`disable_logging()`、`get_execution_log()`
	- 新增类：`AdminServer`、`AdminInfo`、`TokenAuth`
	- 新增类：`ExecutionLog`、`ExecutionLogEntry`、`ExecutionStatus`

- **回调机制**（[#68](../../issues/68)）
	- 新增 `on_change()` 和 `remove_on_change()` 方法，用于监控注册表变更
	- 支持工具注册、移除、启用/禁用事件的回调

- **可观测性 API**
	- 新增 `get_tools_status()` 方法，用于运行时检查工具状态

### 重构

- **将 `dill` 替换为 `cloudpickle`**（[#76](../../issues/76)）
	- 将 executor 中的 `dill.dumps`/`dill.loads` 替换为 `cloudpickle.dumps`/`pickle.loads`
	- 反序列化改用标准库 `pickle`，未来远程 executor 目标环境仅需 Python 标准库
	- 将 pyproject.toml 中的 `dill>=0.4.0` 依赖替换为 `cloudpickle>=3.0.0`

- **现代化类型注解**，适配 Python 3.10+
	- 将 `Union[X, Y]` 替换为 `X | Y` 语法
	- 将 `Optional[X]` 替换为 `X | None`
	- 将 `List`、`Dict`、`Tuple` 替换为小写 `list`、`dict`、`tuple`

### 维护

- 移除 `fake-useragent` 依赖（toolregistry-hub 分离后不再使用）
- 移除旧版 `./docs` 目录（已迁移至 `docs_en`/`docs_zh` worktrees）
- 在 pyproject.toml 中添加 Python 3.10/3.11/3.12/3.13 classifiers

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
	- 新增 `list_tools(include_disabled=True)` 用于管理面板（返回包括已禁用在内的所有工具）
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
