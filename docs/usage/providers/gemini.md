# Google Gemini 集成

???+ note "Changelog"
    New in version: 0.7.0

本指南介绍如何将 ToolRegistry 与 [Google Gemini API](https://ai.google.dev/gemini-api/docs/function-calling) 配合使用。ToolRegistry 可以生成 Gemini 原生的函数声明，并重建 `functionCall` / `functionResponse` 消息以支持多轮对话。

## 设置 ToolRegistry

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
schemas = registry.get_tools_json(api_format="gemini")
```

返回 Gemini 函数声明格式的工具定义：

```json
[
  {
    "name": "add",
    "description": "Add two numbers together.",
    "parameters": {
      "properties": {
        "a": { "title": "A", "type": "number" },
        "b": { "title": "B", "type": "number" }
      },
      "required": ["a", "b"],
      "title": "addParameters",
      "type": "object"
    }
  },
  {
    "name": "subtract",
    "description": "Subtract the second number from the first.",
    "parameters": {
      "properties": {
        "a": { "title": "A", "type": "number" },
        "b": { "title": "B", "type": "number" }
      },
      "required": ["a", "b"],
      "title": "subtractParameters",
      "type": "object"
    }
  }
]
```

## 使用工具 Schema 发送查询

```python
import os
from google import genai

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Wrap schemas in the tools structure Gemini expects
tools = [{"function_declarations": schemas}]

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="I have 15 chestnuts. Joe ate 3. How many do I have left?",
    config={"tools": tools},
)
```

## 提取工具调用

Gemini 在响应中以 `functionCall` 部件的形式返回函数调用：

```python
tool_calls = [
    part for part in response.candidates[0].content.parts
    if hasattr(part, "function_call") and part.function_call
]
```

`functionCall` 部件示例（字典形式）：

```json
{
  "functionCall": {
    "name": "subtract",
    "args": {"a": 15, "b": 3}
  }
}
```

## 执行工具调用

ToolRegistry 原生支持 Gemini 的 `functionCall` 部件：

```python
tool_responses = registry.execute_tool_calls(tool_calls)
```

## 将结果反馈给 LLM

以 Gemini 格式重建对话消息：

```python
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="gemini"
)
```

生成 Gemini 原生的消息结构：

```json
[
  {
    "role": "model",
    "parts": [
      {
        "functionCall": {
          "name": "subtract",
          "args": {"a": 15, "b": 3}
        }
      }
    ]
  },
  {
    "role": "user",
    "parts": [
      {
        "functionResponse": {
          "name": "subtract",
          "response": {"output": "12"}
        }
      }
    ]
  }
]
```

继续对话：

```python
from google.genai.types import Content, Part

# Build conversation history for the next turn
history = [
    Content(role="user", parts=[Part(text="I have 15 chestnuts. Joe ate 3. How many do I have left?")]),
]

# Add the tool call and result messages
for msg in assistant_tool_messages:
    role = msg["role"]
    parts = []
    for p in msg["parts"]:
        if "functionCall" in p:
            parts.append(Part(function_call=p["functionCall"]))
        elif "functionResponse" in p:
            parts.append(Part(function_response=p["functionResponse"]))
    history.append(Content(role=role, parts=parts))

second_response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=history,
)

print(second_response.text)
```

## 完整 Python 脚本

```python
import json
import os

from google import genai
from google.genai.types import Content, Part
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

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

schemas = registry.get_tools_json(api_format="gemini")
tools = [{"function_declarations": schemas}]

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="I have 15 chestnuts. Joe ate 3. How many do I have left?",
    config={"tools": tools},
)

tool_calls = [
    part for part in response.candidates[0].content.parts
    if hasattr(part, "function_call") and part.function_call
]

if tool_calls:
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    assistant_tool_messages = registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses, api_format="gemini"
    )
    print(json.dumps(assistant_tool_messages, indent=2))

    # Build history for continuation
    history = [
        Content(role="user", parts=[Part(text="I have 15 chestnuts. Joe ate 3. How many do I have left?")]),
    ]
    for msg in assistant_tool_messages:
        parts = []
        for p in msg["parts"]:
            if "functionCall" in p:
                parts.append(Part(function_call=p["functionCall"]))
            elif "functionResponse" in p:
                parts.append(Part(function_response=p["functionResponse"]))
        history.append(Content(role=msg["role"], parts=parts))

    second_response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=history,
    )

    print(second_response.text)
```

## 参见

- [Gemini Function Calling 文档](https://ai.google.dev/gemini-api/docs/function-calling)
- [架构概览](../../architecture/overview.md) -- ToolRegistry 如何通过 llm-rosetta 生成多格式 Schema
