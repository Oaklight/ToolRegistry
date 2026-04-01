# MCPToolWrapper

提供异步和同步版本的 MCP (Model Context Protocol) 工具调用的包装器类。

## 概览

`MCPToolWrapper` 是专门为 Model Context Protocol (MCP) 服务器设计的包装器，提供 ToolRegistry 与基于 MCP 的工具之间的无缝通信。它处理 MCP 协议通信的复杂性，包括多种内容类型、传输管理和错误处理。

## 主要特性

- **MCP 协议集成**：全面支持 Model Context Protocol 规范
- **多传输支持**：处理不同的传输类型（HTTP、WebSocket、基于文件）
- **内容类型处理**：支持文本、图像和嵌入式资源内容
- **传输抽象**：透明管理 MCP 传输连接
- **错误弹性**：全面的错误处理和详细日志记录
- **异步/同步兼容**：同时支持异步和同步执行模式

## 架构

MCPToolWrapper 通过 MCP 特定功能扩展了 `BaseToolWrapper`：

### 核心组件

1. **传输管理**：处理 MCP 传输生命周期和通信
2. **内容处理**：处理多种 MCP 内容类型（文本、图像、嵌入式）
3. **协议处理**：管理 MCP 工具发现和执行
4. **错误处理**：保留 MCP 错误并增强上下文信息

### 通信流程

```
工具调用请求
    ↓
参数验证
    ↓
MCP 客户端通信
    ↓
内容类型处理
    ↓
结果规范化
    ↓
ToolRegistry 响应
```

## API 参考

::: toolregistry.mcp.integration.MCPToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 使用示例

### 基本 MCP 工具包装器

```python
from toolregistry.mcp.integration import MCPToolWrapper

# Create wrapper for specific MCP tool
wrapper = MCPToolWrapper(
    transport="ws://localhost:8000",
    name="mcp_calculator",
    params=["a", "b", "operation"]
)

# Execute tool (automatic mode detection)
result = wrapper(a=5, b=3, operation="add")  # Sync
result = await wrapper(a=5, b=3, operation="add")  # Async
```

### 内容类型处理

```python
# Handle different MCP content types
wrapper = MCPToolWrapper(transport, "document_processor", params=["file_path"])

# Text content
result = wrapper(file_path="readme.txt")  # Returns string content

# Image content
result = wrapper(file_path="image.png")  # Returns {"type": "image", "data": ..., "mimeType": "..."}

# Embedded resources
result = wrapper(file_path="data.json")  # Returns parsed JSON or resource content
```

## 内容类型支持

该包装器处理多种 MCP 内容类型：

### 文本内容

```python
# Simple text response
{
    "result": "Calculation completed: 5 + 3 = 8"
}
```

### 图像内容

```python
# Image response
{
    "result": {
        "type": "image",
        "data": "base64_encoded_image_data",
        "mimeType": "image/png"
    }
}
```

### 嵌入式资源

```python
# Embedded text resource
{
    "result": "Embedded file content"
}

# Embedded blob resource
{
    "result": {
        "type": "blob",
        "data": "binary_data",
        "mimeType": "application/octet-stream"
    }
}
```

## 集成模式

### 与 MCP 集成配合使用

```python
from toolregistry import ToolRegistry
from toolregistry.mcp import MCPIntegration

registry = ToolRegistry()
mcp_integration = MCPIntegration(registry)

# Register all tools from MCP server
await mcp_integration.register_mcp_tools_async("ws://localhost:8000")

# Tools are automatically wrapped with MCPToolWrapper
```

### 传输配置

```python
from toolregistry.mcp.integration import MCPToolWrapper

# Different transport types (pass URL strings or file paths directly)
wrapper_ws = MCPToolWrapper("ws://localhost:8000", "remote_tool", params=["input"])
wrapper_http = MCPToolWrapper("http://localhost:8000/mcp", "remote_tool", params=["input"])
wrapper_file = MCPToolWrapper("./mcp_server.py", "local_tool", params=["input"])
```

## 错误处理

该包装器提供全面的错误处理：

- **连接错误**：网络和传输相关的故障
- **协议错误**：MCP 规范合规性问题
- **内容类型错误**：不支持的内容类型处理
- **工具执行错误**：单个工具执行失败

所有错误都会记录完整的堆栈跟踪以便调试，同时保留原始异常行为。

## 传输支持

支持多种 MCP 传输机制：

- **WebSocket**：实时双向通信
- **HTTP**：可流式 HTTP 和基于 SSE 的通信
- **基于文件**：本地脚本执行（`.py`、`.js`）
- **字典配置**：通过命令配置的基于 stdio 的传输

这使得 MCPToolWrapper 成为将 MCP 服务器集成到 ToolRegistry 生态系统的强大适配器。
