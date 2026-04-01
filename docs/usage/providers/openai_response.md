# OpenAI Response API 集成

延续 [基础用法](../basics) 中的简单数学示例，本文介绍如何将 ToolRegistry 与 OpenAI Response API 配合使用。需要注意的是，你可以通过 OpenAI 客户端连接任何提供 OpenAI Response API 的服务商。本指南以 OpenAI 为例进行演示。

## 设置 ToolRegistry

我们创建一个包含两个数学函数的工具注册表：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@registry.register
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b
```

## 导出工具 Schema

```python
schemas = registry.get_schemas(api_format="openai-response") # available since v0.4.13
```

格式化后的 JSON Schema 如下：

```json
[
  {
    "type": "function",
    "name": "add",
    "description": "Add two numbers together.",
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
      "required": [
        "a",
        "b"
      ],
      "title": "addParameters",
      "type": "object"
    },
    "strict": false
  },
  {
    "type": "function",
    "name": "subtract",
    "description": "Subtract the second number from the first.",
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
      "required": [
        "a",
        "b"
      ],
      "title": "subtractParameters",
      "type": "object"
    },
    "strict": false
  }
]
```

注意与 Chat Completion 格式的区别：

- `openai-response` 格式将函数信息（`name`、`description`、`parameters`）作为顶层字段暴露，而非嵌套在 `function` 对象内部。
- 包含一个 `strict` 字段，值为 `false`。请勿修改此值，因为在严格模式下，所有可选参数都会变为必填参数，这与自动 Schema 生成的预期行为不符。

## 使用工具 Schema 发送查询

将工具 JSON Schema 和用户查询提供给 OpenAI 客户端的 Response 接口：

```python
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from the .env file
load_dotenv()

# Configure the OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.openai.com/v1/"),
)

messages = [
    {
        "role": "user",
        "content": "I have 15 chestnuts. Joe ate 3. How many chestnuts do I have left?",
    }
]

# Make the chat completion request
response = client.responses.create(
    model="gpt-4.1-mini",
    input=messages,
    tools=schemas, # Pass the tool schemas here
    tool_choice="auto",
)
```

## 提取工具调用

如果模型决定使用工具，它会返回类型为 `function_call` 的响应。从响应中提取该信息：

```python
tool_calls = []
for each in response.output:
    if each.type == "function_call":
        tool_calls.append(each)
```

函数调用的输出示例：

```python
[ResponseFunctionToolCall(arguments='{"a":15,"b":3}', call_id='call_FbBTgiYFPuLwdk6jNW2JaNQh', name='subtract', type='function_call', id='fc_6855102fc05c819ba4583b9cb0b6b73b07c0143154471823', status='completed')]
```

`tool_calls` 对象是一个 `ResponseFunctionToolCall` 的 `List`。以下属性尤为重要：

- `call_id`：在将结果反馈给 LLM 时需要用到
- **`name`**：要调用的函数名称
- **`arguments`**：传递给函数的参数字典

## 执行工具调用

使用 `ToolRegistry`，你可以轻松处理**所有** `tool_calls` 的执行结果。注意，有时 LLM 可能会同时调用多个工具。

```python
# Execute tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
```

注册表返回的工具执行结果是一个 Python 字典，键为 `tool_call_id`，值为对应的结果：

```json
{ "call_FbBTgiYFPuLwdk6jNW2JaNQh": 12 }
```

## 将结果反馈给 LLM

执行完函数调用后，我们需要在新的请求中将结果返回给模型。

为了在后续与 LLM 的交互中保持工具调用的上下文，我们需要重建两部分信息：

1. 助手决定发起 `tool_calls` 的消息
2. 实际的 `tool_calls` 执行结果

```python
# Construct assistant messages with results
assistant_tool_messages = registry.build_tool_call_messages(
    tool_calls, tool_responses, api_format="openai-response"
)
```

```json
[
  {
    "arguments": "{\"a\":15,\"b\":3}",
    "call_id": "call_A8O8pkZJGgZlGrcF3nhxv7II",
    "name": "subtract",
    "type": "function_call",
    "id": null,
    "status": null
  },
  {
    "type": "function_call_output",
    "call_id": "call_A8O8pkZJGgZlGrcF3nhxv7II",
    "output": "12"
  }
]
```

然后将这些重建的消息追加到之前发送给 LLM 的消息列表中。

```python
messages.extend(assistant_tool_messages)

# Send the results back to the model
response = client.responses.create(
    model="gpt-4.1-mini",
    input=messages,
    tools=registry.get_schemas(api_format="openai-response"),
    tool_choice="auto",
)

# Print final response
if response.output:
    print(response.output_text)
```

## 最终结果与注意事项

LLM 在处理完工具执行结果后，会返回最终答案：

```markdown
You have **12 chestnuts** left after Joe ate 3.
```

### 重要的实现说明

实现时应处理[连续函数调用](../../examples/consecutive_tool_calls)的情况，因为对话可能需要多轮工具调用，每次 LLM 的响应都可能触发新的工具调用。

错误处理至关重要：在执行工具调用前，始终需要验证参数的合法性（ToolRegistry 已自动完成此操作）。需要处理工具可能失败或返回错误的情况，并考虑为长时间运行的操作添加超时机制。

状态管理涉及维护完整的对话历史（包括所有工具调用及其响应）、跟踪工具执行顺序以便调试，以及考虑对话状态的持久化。

性能方面需要注意减少不必要的工具调用、在适当时缓存频繁的工具响应结果，以及监控和优化工具执行时间。

## 完整 Python 脚本

以下是本示例使用的完整脚本。

```python
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@registry.register
def subtract(a: float, b: float) -> float:
    """Subtract the second number from the first."""
    return a - b


print(json.dumps(registry.get_schemas(api_format="openai-response"), indent=2))

# Set up OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)


messages = [
    {
        "role": "user",
        "content": "I have 15 chestnuts. Joe ate 3. How many chestnuts do I have left?",
    }
]

# Make the chat completion request
response = client.responses.create(
    model=model_name,
    input=messages,
    tools=registry.get_schemas(api_format="openai-response"),
    tool_choice="auto",
)

tool_calls = []
for each in response.output:
    if each.type == "function_call":
        tool_calls.append(each)
print(tool_calls)

# Execute tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
print(tool_responses)

# Construct assistant messages with results
assistant_tool_messages = registry.build_tool_call_messages(
    tool_calls, tool_responses, api_format="openai-response"
)
print(json.dumps(assistant_tool_messages, indent=2))

messages.extend(assistant_tool_messages)

# Send the results back to the model
response = client.responses.create(
    model=model_name,
    input=messages,
    tools=registry.get_schemas(api_format="openai-response"),
    tool_choice="auto",
)

# Print final response
if response.output:
    print(response.output_text)
```
