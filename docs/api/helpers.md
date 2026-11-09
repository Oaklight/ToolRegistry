# 辅助类

支持 ToolRegistry 库核心功能的实用类和辅助函数。

## 参数模型

工具函数的参数验证和 Schema 生成。`ArgModelBase` 根据函数签名动态创建 Pydantic 模型，用于运行时参数验证。

::: toolregistry.parameter_models
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false

## 实用工具

`toolregistry.utils` 是兼容层：它重新导出下游包导入的所有辅助函数，因此现有导入保持可用。实现按职责就近放置：工具名称标准化与注册过滤器在 `toolregistry._names`，基础 URL 的 HTTP 客户端与 `HttpClientConfig` 在 `toolregistry._http`，工具结果编码在 `toolregistry._serialisation`。

::: toolregistry.utils
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false
