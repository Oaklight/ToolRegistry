# ToolRegistry

[English](README.md)

一个用于结构化管理和执行工具的 Python 库。

## 特性

- 工具注册与管理
- 为工具参数生成 JSON Schema
- 工具执行与结果处理
- 支持同步和异步工具

## 安装

基础安装:

```bash
pip install toolregistry
```

安装 MCP 扩展 (需要 **Python >= 3.10**):

```bash
pip install "toolregistry[mcp]"
```

## 示例

### OpenAI 实现

文件 [openai_tool_usage_example.py](examples/openai_tool_usage_example.py) 展示了如何将 ToolRegistry 与 OpenAI 的 API 集成。

### Cicada 实现

文件 [cicada_tool_usage_example.py](examples/cicada_tool_usage_example.py) 演示了如何使用 ToolRegistry 与 Cicada 多模态模型。

## OpenAI 集成

ToolRegistry 与 OpenAI 的 API 无缝集成。以下是一些常见的用法：

### 获取用于 OpenAI 的工具 JSON

```python
tools_json = registry.get_tools_json()
# 将此 JSON 用于 OpenAI 的 API，以提供可用工具
```

### 执行工具调用

```python
# 假设 tool_calls 是从 OpenAI 的 API 接收到的调用列表
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
# 获取一个可调用函数
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # 输出: 3
```

## 文档

完整的文档请访问 [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。
