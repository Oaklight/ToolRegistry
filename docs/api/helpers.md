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

管理面板的 Python 来源预览只列出在模块中定义的函数。由于 `toolregistry.utils` 现在是兼容层，预览它不会再列出已移走的函数；请在 `toolregistry._names`、`toolregistry._http` 或 `toolregistry._serialisation` 中注册这些函数。

::: toolregistry.utils
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false
