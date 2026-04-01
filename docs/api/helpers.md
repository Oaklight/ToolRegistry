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

库中通用的实用函数，包括工具名称标准化和用于 OpenAPI 集成的 HTTP 客户端配置。

::: toolregistry.utils
    options:
        show_source: true
        show_root_heading: true
        show_root_toc_entry: false
