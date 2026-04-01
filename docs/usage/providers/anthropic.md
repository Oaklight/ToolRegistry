# Anthropic 集成

???+ note "Changelog"
    New in version: 0.7.0

本指南介绍如何将 ToolRegistry 与 [Anthropic API](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)（Claude）配合使用。ToolRegistry 可以生成 Anthropic 原生的工具 Schema，并重建 `tool_use` / `tool_result` 消息以支持多轮对话。

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
schemas = registry.get_schemas(api_format="anthropic")
```

返回 Anthropic 格式的工具定义：

```json
[
  {
    "name": "add",
    "description": "Add two numbers together.",
    "input_schema": {
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
    "input_schema": {
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
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

messages = [
    {"role": "user", "content": "I have 15 chestnuts. Joe ate 3. How many do I have left?"}
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=schemas,
    messages=messages,
)
```

## 提取工具调用

Anthropic 以 `tool_use` 内容块的形式返回工具调用：

```python
tool_calls = [block for block in response.content if block.type == "tool_use"]
```

`tool_use` 块示例：

```json
{
  "type": "tool_use",
  "id": "toolu_01A09q90qw90lq917835lq9",
  "name": "subtract",
  "input": {"a": 15, "b": 3}
}
```

## 执行工具调用

ToolRegistry 原生支持 Anthropic 的 `tool_use` 块：

```python
tool_responses = registry.execute_tool_calls(tool_calls)
```

返回一个字典，键为工具调用 ID，值为执行结果：

```json
{"toolu_01A09q90qw90lq917835lq9": "12"}
```

## 将结果反馈给 LLM

以 Anthropic 格式重建对话消息：

```python
assistant_tool_messages = registry.build_tool_call_messages(
    tool_calls, tool_responses, api_format="anthropic"
)
```

生成 Anthropic 原生的消息结构：

```json
[
  {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01A09q90qw90lq917835lq9",
        "name": "subtract",
        "input": {"a": 15, "b": 3}
      }
    ]
  },
  {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
        "content": "12"
      }
    ]
  }
]
```

将消息追加到对话中并获取最终答案：

```python
messages.extend(assistant_tool_messages)

second_response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=messages,
)

print(second_response.content[0].text)
```

## 完整 Python 脚本

```python
import json
import os

import anthropic
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

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

messages = [
    {"role": "user", "content": "I have 15 chestnuts. Joe ate 3. How many do I have left?"}
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=registry.get_schemas(api_format="anthropic"),
    messages=messages,
)

tool_calls = [block for block in response.content if block.type == "tool_use"]

if tool_calls:
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    assistant_tool_messages = registry.build_tool_call_messages(
        tool_calls, tool_responses, api_format="anthropic"
    )
    print(json.dumps(assistant_tool_messages, indent=2))

    messages.extend(assistant_tool_messages)
    second_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=messages,
    )

    print(second_response.content[0].text)
```

## 参见

- [Anthropic Tool Use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [架构概览](../../architecture/overview.md) -- ToolRegistry 如何通过 llm-rosetta 生成多格式 Schema
