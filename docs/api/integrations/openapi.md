# OpenAPI 集成

本节介绍 ToolRegistry 库的 OpenAPI/Swagger 集成功能。

## 架构概览

OpenAPI 集成旨在基于 OpenAPI 规范自动发现和注册 REST API 端点为工具。该架构采用三层设计：

### 核心组件

1. **OpenAPIToolWrapper**：一个包装器类，提供同步和异步 HTTP 客户端方法用于 API 调用

   - 处理 GET、POST、PUT、DELETE 请求
   - 支持参数处理和验证
   - 与 httpx 集成实现 HTTP 通信

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

## 模块工具

### OpenAPI 工具函数

用于 OpenAPI 处理的实用函数。

::: toolregistry.integrations.openapi.utils
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
