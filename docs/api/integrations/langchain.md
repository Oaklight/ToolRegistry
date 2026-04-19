# LangChain 集成

本节介绍 ToolRegistry 库的 LangChain 集成功能。

## 架构概览

LangChain 集成实现了 LangChain 工具与 ToolRegistry 生态系统之间的无缝互操作。该集成允许在 ToolRegistry 框架中使用 LangChain 丰富的工具生态系统：

### 核心组件

1. **LangChainToolWrapper**：一个包装器类，桥接 LangChain 工具与 ToolRegistry 的统一接口

   - 提供同步（`_run`）和异步（`_arun`）执行方法
   - 管理 LangChain 和 ToolRegistry 格式之间的参数映射
   - 处理错误传播和日志记录

2. **LangChainTool**：一个工具类，包装 LangChain BaseTool 实例

   - 保留原始工具元数据和描述
   - 将 LangChain 输入模式转换为 ToolRegistry 格式
   - 支持命名空间，用于工具组织

3. **LangChainIntegration**：主集成类，协调桥接流程
   - 管理从 LangChain 工具到 ToolRegistry 工具的转换
   - 支持单个工具和批量注册模式
   - 处理模式转换和规范化

### 设计理念

- **非侵入式集成**：保留原始 LangChain 工具行为
- **模式兼容性**：LangChain 和 ToolRegistry 模式之间的自动转换
- **错误透明性**：保留原始 LangChain 异常并增强上下文信息
- **异步支持**：完全兼容 LangChain 的异步执行模型

### 主要特性

- 直接与 LangChain 的 `BaseTool` 实例集成
- 从 LangChain 到 ToolRegistry 格式的自动模式转换
- 支持同步和异步执行模式
- 命名空间支持，用于组织 LangChain 工具
- 保留原始 LangChain 工具的错误处理和日志记录
- 最小开销——无需额外依赖或转换

### 使用模式

- **单工具集成**：注册单个 LangChain 工具
- **工具集合**：从集合中集成多个 LangChain 工具
- **命名空间组织**：将 LangChain 工具分组到公共命名空间下
- **错误处理**：保持 LangChain 原始异常行为并增强上下文

## API 参考

### LangChainToolWrapper

提供异步和同步版本的 LangChain 工具调用的包装器类。

::: toolregistry.integrations.langchain.integration.LangChainToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### LangChainTool

保留原始函数元数据的 LangChain 工具包装器类。

::: toolregistry.integrations.langchain.integration.LangChainTool
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### LangChainIntegration

处理与 LangChain 工具集成以进行注册的类。

::: toolregistry.integrations.langchain.integration.LangChainIntegration
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 模块概览

### LangChain 模块

LangChain 集成主模块。

::: toolregistry.integrations.langchain
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
