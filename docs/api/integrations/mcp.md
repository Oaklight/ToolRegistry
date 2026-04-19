# MCP 集成

本节介绍 ToolRegistry 库的 Model Context Protocol (MCP) 集成功能。

## 架构概览

MCP 集成实现了与 Model Context Protocol 服务器的无缝通信，使 LLM 应用能够使用外部 MCP 服务器提供的工具。该架构采用客户端-服务器通信模型：

### 核心组件

1. **MCPToolWrapper**：一个包装器类，提供与 MCP 服务器的同步和异步通信

   - 通过 MCP 协议处理工具执行
   - 支持多种内容类型（文本、图像、嵌入式资源）
   - 管理客户端传输和通信生命周期

2. **MCPTool**：一个工具类，包装 MCP 工具规范

   - 保留原始工具元数据和描述
   - 将 MCP 模式转换为 ToolRegistry 格式
   - 支持命名空间组织

3. **MCPIntegration**：主集成类，协调服务器通信
   - 管理与 MCP 服务器的客户端连接
   - 从服务器发现可用工具
   - 为不同连接类型处理传输抽象

### 通信架构

- **传输层**：支持多种传输类型（HTTP、WebSocket、基于文件）
- **协议层**：实现 MCP 规范用于工具发现和执行
- **内容处理**：处理多种内容类型及后处理

### 主要特性

- 支持多种传输类型（URL、文件路径、服务器实例）
- 从 MCP 服务器自动发现工具
- 多格式内容支持（文本、图像、嵌入式资源）
- 命名空间管理，用于工具组织
- 健壮的错误处理和详细日志记录
- 同步和异步两种操作模式

### 传输支持

该集成支持多种传输机制：

- HTTP/HTTPS 端点（可流式 HTTP、SSE）
- WebSocket 连接
- 本地文件路径（Python 脚本、JavaScript 文件）
- 基于字典的 stdio 配置

## API 参考

### MCPToolWrapper

提供异步和同步版本的 MCP 工具调用的包装器类。

::: toolregistry.integrations.mcp.integration.MCPToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### MCPTool

保留原始函数元数据的 MCP 工具包装器类。

::: toolregistry.integrations.mcp.integration.MCPTool
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### MCPIntegration

处理与 MCP 服务器集成以进行工具注册的类。

::: toolregistry.integrations.mcp.integration.MCPIntegration
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 模块工具

### MCPClient

基于官方 `mcp` SDK 的最小 MCP 客户端适配器。支持 stdio、SSE、可流式 HTTP 和 WebSocket 传输。

::: toolregistry.integrations.mcp.client.MCPClient
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

### MCP 模块

MCP 集成主模块。

::: toolregistry.integrations.mcp
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
