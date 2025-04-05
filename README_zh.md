# ToolRegistry

[English Version](README_en.md)

一个用于结构化管理和执行工具的 Python 库。

## 功能特性

- 工具注册与管理
- 工具参数的 JSON Schema 生成
- 工具执行与结果处理
- 支持同步和异步工具

## 安装

### 基础安装

安装核心包 (需要 **Python >= 3.8**):

```bash
pip install toolregistry
```

### 安装额外支持模块

额外模块可以通过在方括号内指定扩展名进行安装。例如，要安装特定的额外支持模块:

```bash
pip install toolregistry[mcp,openapi]
```

下表总结了可用的扩展模块:

| 扩展模块 | Python 版本要求   | 示例命令                          |
|----------|-------------------|-----------------------------------|
| mcp      | Python >= 3.10    | pip install toolregistry[mcp]     |
| openapi  | Python >= 3.8     | pip install toolregistry[openapi] |

## 示例

### OpenAI 实现

[openai_tool_usage_example.py](examples/openai_tool_usage_example.py) 展示了如何将 ToolRegistry 与 OpenAI API 集成。

### Cicada 实现

[cicada_tool_usage_example.py](examples/cicada_tool_usage_example.py) 演示了如何在 Cicada MultiModalModel 中使用 ToolRegistry。

## OpenAI 集成

ToolRegistry 可以无缝集成 OpenAI API，以下是常见使用模式：

### 获取 OpenAI 工具 JSON

```python
tools_json = registry.get_tools_json()
# 将此与 OpenAI API 一起使用以提供可用工具
```

### 执行工具调用

```python
# 假设 tool_calls 是从 OpenAI API 接收的
tool_responses = registry.execute_tool_calls(tool_calls)
```

### 恢复助手消息

```python
# 执行工具调用后
messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
# 使用这些消息继续对话
```

### 手动工具执行

```python
# 获取可调用函数
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # 输出: 3
```

## MCP 集成

ToolRegistry 为 MCP (Model Context Protocol) 工具提供一流支持：

### 基础用法

```python
from toolregistry import ToolRegistry

# 创建注册表并注册 MCP 工具
registry = ToolRegistry()
registry.register_mcp_tools("http://localhost:8000/mcp/sse")

# 获取包含 MCP 工具的所有工具 JSON
tools_json = registry.get_tools_json()
```

### 调用 MCP 工具

```python
# 使用注册表同步调用
result = registry["echo_tool"]("测试同步消息")

# 直接使用工具同步调用
echo_tool = registry.get_callable("echo_tool")
result = echo_tool.run({"message": "测试同步消息"})

# 使用注册表异步调用 (需要 await 和 asyncio.run)
result = await registry["echo_tool"]("测试消息")

# 直接使用工具异步调用 (需要 await 和 asyncio.run)
result = await echo_tool.arun({"message": "测试同步消息"})
```

## 文档

完整文档请访问 [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。
