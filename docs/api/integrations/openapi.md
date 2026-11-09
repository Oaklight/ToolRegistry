# OpenAPI 集成

本节介绍 ToolRegistry 库的 OpenAPI/Swagger 集成功能。

## 架构概览

OpenAPI 集成旨在基于 OpenAPI 规范自动发现和注册 REST API 端点为工具。该架构采用三层设计：

### 核心组件

1. **OpenAPIToolWrapper**：一个包装器类，提供同步和异步 HTTP 客户端方法用于 API 调用

   - 处理 GET、POST、PUT、DELETE 请求
   - 支持参数处理和验证
   - 使用内置 HTTP 客户端实现 HTTP 通信

2. **OpenAPITool**：一个工具类，保留从 OpenAPI 规范中提取的函数元数据

   - 从 OpenAPI 规范自动生成参数模式
   - 规范化工具名称和描述
   - 支持命名空间

3. **OpenAPIIntegration**：主集成类，协调注册流程
   - 解析 OpenAPI 规范
   - 为每个端点创建工具实例
   - 支持同步和异步注册

### 设计模式

- **工厂模式**：`OpenAPITool.from_openapi_spec()` 从规范创建工具实例
- **包装器模式**：`OpenAPIToolWrapper` 为 HTTP 操作提供统一接口
- **模板方法**：同步和异步版本遵循相似的模式，支持 async/await

### 主要特性

- 从 OpenAPI 模式自动提取参数
- 支持查询参数、路径参数和请求体
- 命名空间支持，用于工具组织
- 完整的 async/await 兼容性
- 自动 HTTP 状态错误处理

## API 参考

### OpenAPIToolWrapper

提供同步和异步方法用于 OpenAPI 工具调用的包装器类。

::: toolregistry.integrations.openapi.integration.OpenAPIToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### OpenAPITool

保留函数元数据的 OpenAPI 工具包装器类。

::: toolregistry.integrations.openapi.integration.OpenAPITool
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### OpenAPIIntegration

处理与 OpenAPI 服务集成以进行工具注册的类。

::: toolregistry.integrations.openapi.integration.OpenAPIIntegration
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 刷新文档

`OpenAPIIntegration.refresh()` 使用已保存的 ETag 重新读取注册时的文档。
`304` 返回 `skipped` 且不做任何改动：不重建路由，也不更新
`last_refreshed_at`。文档发生变化时会与现有工具做 diff：运维手动禁用的名称
仍保持禁用，已消失的路径会被注销，定义未变的工具保留其注册表状态。

base URL 会跟随文档，但有边界。注册时文档在 `servers[0]` 中写明的 URL 会被
记住；只有当前客户端配置仍等于该记忆值时，刷新才会采纳移动后的
`servers[0]`——调用方显式提供的 base URL 永远不会被替换。只有刷新真正要采纳的
那一个条目会接受出站地址策略检查；不会被拨打的条目既不校验也不解析，而显式
override 会让文档的 `servers` 与本次刷新无关。模板化条目（如
`https://{region}.example.com`）在替换前无法解析，因此既不会被采纳也不会被
检查：当前 base URL 保持不变，文档的其余变更照常生效。采纳会重建每个工具的
包装器，包括定义未变的操作；这种替换不计入 `updated`，而由
`RefreshResult.base_url_changed` 表示。被拒绝的候选条目会抛出
`UnsafeAddressError`，工具、配置与已保存的文档都保持不变。

`forget_tracked_tools(names)` 供「在两次刷新之间移除了工具」的调用方使用——例如
校验步骤丢掉了 schema 无法接受的工具。没有它，下一次刷新会认为该名称仍被跟踪但
不在注册表中，从而永远不会重新注册；调用后，文档修好时名称会回来。它只修改跟踪
集合：注册表与事件由调用方自己处理。

`ToolRegistry.openapi_integrations` 按创建顺序返回这些集成，因此刚完成注册的
调用方可以直接取最后一个元素，而不必读取私有列表。

## 模块工具

### OpenAPI 工具函数

用于 OpenAPI 处理的实用函数。

::: toolregistry.integrations.openapi.utils
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
