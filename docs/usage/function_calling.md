# LLM 函数调用

继续我们在[基础用法](basics)中的简单数学示例，本文档解释如何将工具注册表与 OpenAI API 一起使用。请注意，您可以将 OpenAI 客户端与任何提供 OpenAI 兼容 API 的 API 提供者一起使用。在本指南中，我们将使用 DeepSeek 作为示例。

回想一下，我们使用 `registry.get_tools_json()` 获得了两个数学函数的 JSON 模式：

```json
[
  {
    "type": "function",
    "function": {
      "name": "add",
      "description": "将两个数字相加。",
      "parameters": {
        "properties": {
          "a": {
            "title": "A",
            "type": "number"
          },
          "b": {
            "title": "B",
            "type": "number"
          }
        },
        "required": ["a", "b"],
        "title": "addParameters",
        "type": "object"
      },
      "is_async": false
    }
  },
  {
    "type": "function",
    "function": {
      "name": "subtract",
      "description": "从第一个数字中减去第二个数字。",
      "parameters": {
        "properties": {
          "a": {
            "title": "A",
            "type": "integer"
          },
          "b": {
            "title": "B",
            "type": "integer"
          }
        },
        "required": ["a", "b"],
        "title": "subtractParameters",
        "type": "object"
      },
      "is_async": false
    }
  }
]
```

## 提供带工具的聊天查询

将工具 JSON 模式提供给 OpenAI 客户端的聊天完成接口：

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

# 从 .env 文件加载环境变量
load_dotenv()

# 配置 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)

messages = [
    {
        "role": "user",
        "content": "我有 15 个栗子。Joe 吃了 3 个。我还剩多少个栗子？",
    }
]
# 发送聊天完成请求
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=registry.get_tools_json(), # 这里我们提供模式
    tool_choice="auto",
)
```

## 什么是 `tool_calls`？

如果模型（LLM）决定使用工具，它将在响应消息中返回 `tool_calls`：

```python
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)
```

```python
[ChatCompletionMessageToolCall(id='call_egkg4evbb19d8012bex83v8a', function=Function(arguments='{"a":15,"b":3}', name='subtract'), type='function', index=0)]
```

`tool_calls` 对象是 `ChatCompletionMessageToolCall` 对象的 `List`。以下属性特别有用：

- `id`：这是我们将结果反馈给 LLM 时需要的
- **`function`**：**这是核心，包含目标函数的参数和名称**
- `index`：在非流模式下不太有用，但如果您流式传输聊天结果，这是组合完整 tool_calls 信息的关键

## 执行工具调用

使用 `ToolRegistry`，您可以轻松处理来自**所有** `tool_calls` 的结果。请注意，有时 LLM 可能决定同时调用多个工具。

```python
# 执行工具调用
tool_responses = registry.execute_tool_calls(tool_calls)
print(tool_responses)
```

注册表的工具执行结果作为 Python 字典返回，将 `tool_call_id` 映射到结果：

```json
{ "call_0_bfa567b8-2f10-4113-953a-56e87b664e0f": 12 }
```

## 将结果反馈给 LLM

执行工具调用后，我们仍需要在 LLM 能够回答原始问题之前告知它结果。

我们需要构造工具结果消息并将它们包含在聊天历史中，以便 LLM 能够理解上下文：

```python
# 构造带结果的助手消息
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses
)
print(assistant_tool_messages)
```

为了维护后续 LLM 交互的工具调用上下文，我们需要重构：

1. 助手做出 `tool_calls` 的决定
2. 实际的 `tool_calls` 结果

```json
[
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_0_bfa567b8-2f10-4113-953a-56e87b664e0f",
        "type": "function",
        "function": {
          "name": "subtract",
          "arguments": "{\"a\":15,\"b\":3}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "content": "subtract --> 12",
    "tool_call_id": "call_0_bfa567b8-2f10-4113-953a-56e87b664e0f"
  }
]
```

然后我们用这些重构的消息扩展之前发送给第一个 LLM 的消息。

```python
messages.extend(assistant_tool_messages)

# 将结果发送回模型
second_response = client.chat.completions.create(
    model="deepseek-chat", messages=messages
)

# 打印最终响应
print(second_response.choices[0].message.content)
```

## 最终结果和注意事项

LLM 在处理工具执行结果后将返回最终答案：

```markdown
在 Joe 吃了 3 个栗子后，您还剩 **12 个栗子**。
```

### 重要实现注意事项

实现应该处理[连续函数调用](examples)，因为对话可能需要多轮工具调用，LLM 的每个响应都可能触发新的工具调用。

错误处理至关重要；在执行前始终验证工具调用参数，ToolRegistry 会为您执行此操作。处理工具可能失败或返回错误的情况，并考虑长时间运行操作的超时机制。

状态管理涉及维护对话历史，包括所有工具调用和响应，跟踪工具执行序列以进行调试，并考虑对话状态持久化。

性能考虑包括最小化不必要的工具调用，在适当时缓存频繁的工具响应，以及监控和优化工具执行时间。

## 完整的 Python 脚本

以下是本演示中使用的完整脚本。

```python
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# 从 .env 文件加载环境变量
load_dotenv()

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """将两个数字相加。"""
    return a + b


@registry.register
def subtract(a: int, b: int) -> int:
    """从第一个数字中减去第二个数字。"""
    return a - b


# 设置 OpenAI 客户端
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)


messages = [
    {
        "role": "user",
        "content": "我有 15 个栗子。Joe 吃了 3 个。我还剩多少个栗子？",
    }
]

# 发出聊天完成请求
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=registry.get_tools_json(),
    tool_choice="auto",
)

# 使用 ToolRegistry 处理工具调用
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)

    # 执行工具调用
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    # 构造带结果的助手消息
    assistant_tool_messages = registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses
    )
    print(assistant_tool_messages)

    messages.extend(assistant_tool_messages)

    # 将结果发送回模型
    second_response = client.chat.completions.create(
        model="deepseek-chat", messages=messages
    )

    # 打印最终响应
    print(second_response.choices[0].message.content)
