---
title: 消息构建
summary: 为工具调用的往返构建对话消息
description: 如何使用 build_assistant_message、build_tool_response 和 build_tool_call_messages 构建 LLM 对话历史
keywords: 消息构建, 工具调用, 助手消息, 工具响应, 对话历史
author: Oaklight
---

# 消息构建

执行工具调用后，需要构建对话消息以便 LLM 处理结果并继续对话。ToolRegistry 提供了三个函数来完成此任务。

## 概览

| 函数 | 层级 | 输入 | 输出 |
|------|------|------|------|
| `build_assistant_message()` | 模块级 | `list[ToolCall]` | 包含工具调用请求的助手消息 |
| `build_tool_response()` | 模块级 | `dict[str, str]` | 工具结果消息 |
| `build_tool_call_messages()` | `ToolRegistry` 方法 | 原始工具调用 + 响应 | 助手消息 + 工具消息的组合 |

大多数情况下，只需使用 `build_tool_call_messages()` —— 这个高层便利方法会处理所有细节。

## `build_tool_call_messages()`

将助手消息（LLM 决定调用的工具）和工具结果组合成下一轮 LLM 调用所需的消息格式。

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

# LLM 返回 tool_calls 后执行：
tool_responses = registry.execute_tool_calls(tool_calls)

# 构建下一轮对话消息
messages = registry.build_tool_call_messages(
    tool_calls, tool_responses, api_format="openai-chat"
)

# 扩展对话历史
conversation.extend(messages)
```

### Gemini ID 对齐

Gemini 上游不提供工具调用 ID —— ToolRegistry 在内部生成。`build_tool_call_messages()` 通过基于位置的 ID 重映射透明地处理此问题：它按位置将 `tool_calls` 中生成的 ID 与 `tool_responses` 中的 ID 对齐。

!!! warning "不要重排 tool_calls"
    在调用 `execute_tool_calls()` 和 `build_tool_call_messages()` 之间，**不得**重新排列 `tool_calls` 列表。两个方法按相同顺序处理工具调用，Gemini 格式依赖于这种位置对齐。重排会导致输出中的函数名不匹配。

## `build_assistant_message()`

低级函数，仅重建包含工具调用请求的助手侧消息。

```python
from toolregistry.types.common import build_assistant_message, ToolCall

tool_calls = [
    ToolCall(id="call_1", name="add", arguments='{"a": 1, "b": 2}')
]

# 以目标格式返回助手消息
assistant_msg = build_assistant_message(tool_calls, api_format="openai-chat")
```

### 作用域与边界

此函数**仅处理工具调用**。不处理以下内容：

- **`content`** —— 与工具调用一起返回的文本内容
- **`thinking` / `reasoning_content`** —— 第三方 OpenAI 兼容 API 的思维链
- **`thought_signature`** —— Google 的思考元数据
- **任何其他供应商特定字段**

如果 LLM 返回混合内容（文本 + 工具调用），你必须自行从原始响应中保留非工具调用字段。

## `build_tool_response()`

低级函数，从执行响应中重建工具结果消息。

```python
from toolregistry.types.common import build_tool_response

tool_responses = {"call_1": "3.0", "call_2": "7.0"}

# 以目标格式返回工具结果消息
tool_msgs = build_tool_response(tool_responses, api_format="openai-chat")
```

### Gemini 名称解析

对于 Gemini 格式，`functionResponse` 需要函数**名称**（而非调用 ID）。传入 `tool_calls` 以启用名称解析：

```python
tool_msgs = build_tool_response(
    tool_responses,
    api_format="gemini",
    tool_calls=generic_tool_calls,  # Gemini 格式必需
)
```

不传入 `tool_calls` 时，函数将使用调用 ID 作为名称，这会生成不正确的 Gemini 消息。

## API 格式值

`api_format` 参数接受以下值：

| 值 | 说明 |
|----|------|
| `"openai-chat"` | OpenAI Chat Completion 格式（默认，规范名称） |
| `"openai-response"` | OpenAI Response API 格式 |
| `"anthropic"` | Anthropic Messages API 格式 |
| `"gemini"` | Google Gemini API 格式 |
| `"openai"` | **已弃用** —— `"openai-chat"` 的别名 |
| `"openai-chatcompletion"` | **已弃用** —— `"openai-chat"` 的别名 |

使用已弃用的格式名称会触发 `DeprecationWarning`。

## 风险提示

| 风险 | 影响函数 | 缓解措施 |
|------|---------|---------|
| 重排 `tool_calls` 破坏 Gemini ID 对齐 | `build_tool_call_messages()` | 在 `execute_tool_calls()` 和 `build_tool_call_messages()` 之间不要重排 |
| 缺少 `tool_calls` 参数导致 Gemini 函数名错误 | `build_tool_response()` | Gemini 格式下始终传入 `tool_calls` |
| 混合内容（文本 + 工具调用）被静默丢弃 | `build_assistant_message()` | 自行从原始响应中保留非工具调用内容 |
| `tool_responses` 字典顺序对 Gemini 有影响 | `build_tool_call_messages()` | Python 3.7+ 字典保持插入顺序；不要重新构建字典 |

## 弃用名称

以下旧名称仍然可用，但会触发 `DeprecationWarning`：

| 旧名称 | 新名称 |
|--------|--------|
| `recover_assistant_message()` | `build_assistant_message()` |
| `recover_tool_message()` | `build_tool_response()` |
| `registry.recover_tool_call_assistant_message()` | `registry.build_tool_call_messages()` |
| `registry.get_tools_json()` | `registry.get_schemas()` |
