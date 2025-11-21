# 基础用法

本页面介绍注册工具、处理工具调用以及将工具注册表桥接到 OpenAI API 的基本用法。
让我们使用一个简单的数学工具注册表进行演示。

## 注册工具

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """将两个数字相加。"""
    return a + b


@registry.register
def subtract(a: int, b: int) -> int:
    """从第一个数字中减去第二个数字。"""
    return a - b
```

## 访问可用工具名称

您可以通过调用 `get_available_tools()` 函数来访问可用工具列表：

```python
available_tools = registry.get_available_tools()

print(available_tools) # ['add', 'subtract']
```

您可以通过以下方式访问可用工具：

1. 作为 Python `Callable`

   您可以通过 `get_callable` 显式获取

   ```python
   add_func = registry.get_callable('add')
   print(type(add_func)) # <class 'function'>

   add_result = add_func(1, 2)
   print(add_result) # 3
   ```

   您也可以通过 `__getitem__` 方法访问

   ```python
   add_func = registry['add']
   print(type(add_func)) # <class 'function'>

   add_result = add_func(4, 5)
   print(add_result) # 9
   ```

2. 作为 `toolregistry.tool.Tool`

   使用 `get_tool` 显式暴露 Tool 接口。

   ```python
   add_tool = registry.get_tool("add")
   print(type(add_tool)) # <class 'toolregistry.tool.Tool'>

   value = add_tool.run({"a": 7, "b": 8})
   print(value) # 15.0
   ```

   注意结果是 15.0 而不是 15，因为 `add` 函数的类型提示将 `a` 和 `b` 都指定为浮点数。在 `toolregistry.tool.Tool` 中进行模式验证时，整数输入被转换为浮点数（7.0 和 8.0），从而产生浮点数输出。

## 工具的 JSON 模式

使用 ToolRegistry 级别的 `get_tools_json` 方法来检索与目标 API 的函数调用接口兼容的 JSON 模式。

我们使用每个 API 标准的函数调用接口来处理集成，因为函数调用是每个标准中启用工具使用的通用核心功能。

```python
# 获取 OpenAI 的工具 JSON
tools_json = registry.get_tools_json(api_format="openai-chatcompletion")
```

从 v0.4.13 开始，我们在 `get_tools_json` 方法中添加了一个新参数 `api_format`，用于指定工具 JSON 的 API 格式。

api_format 可以是以下之一，未来将添加更多：

- [x] `openai-chatcompletion` 或 `openai`（默认）
- [x] `openai-response`（从 v0.4.13 开始）
- [ ] `anthropic`（开发中）
- [ ] `gemini`（开发中）

例如 `openai-chatcompletion`，您将看到以下内容。同时，您可以看到函数 `add` 和 `subtract` 中参数 `a` 的 `type` 差异，一个是 `number`，另一个是 `integer`。

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
    }
  }
]
```

如果您对**工具级别**的 JSON 模式感兴趣，可以使用以下任一方法：

```python
registry.get_tools_json(tool_name="add", api_format="openai-chatcompletion") # 您需要指定工具名称
add_tool.get_json_schema(api_format="openai-chatcompletion")
add_tool.describe(api_format="openai-chatcompletion") # 更简单的接口，get_json_schema 的别名
```

```json
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
    }
  }
}
```

## 执行工具

从 LLM 响应中获得工具调用指令后，您可以使用 `ToolRegistry` 类的 `execute_tool_calls` 方法执行它们。此方法接受工具调用列表并返回工具响应列表。每个工具响应包含工具执行的结果和其他元数据。

```python
# tool_calls 来自 LLMAPI 响应。这是 OpenAI Chat Completion API 的模拟示例。
tool_calls = [
    {
        "id": "call_123",
        "type": "function",
        "function": {
            "name": "add",
            "arguments": '{"a": 1, "b": 2}'
        }
    }
]
tool_responses = registry.execute_tool_calls(tool_calls)
```

默认情况下，`execution_mode` 参数设置为 `process`，这意味着工具调用将使用多个进程并行执行。有关 `execution_mode` 参数的更多信息，请参阅[并发模式：线程模式和进程模式](concurrency_modes)部分。

结果将打包为字典，工具调用 ID 作为键，结果作为值。

请阅读 [OpenAI Chat Completion 集成](providers/openai_chat)或特定提供者集成指南，了解详细示例和逐步分解说明。

### 手动工具执行

您也可以通过从注册表获取其可调用函数来手动执行工具。

```python
# 获取可调用函数
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # 输出：3
```

## 重构助手和工具调用消息

`ToolRegistry` 类提供 `recover_tool_call_assistant_message` 来为 LLM 重构助手和工具调用消息。如果您想简化向 LLM 发送消息的过程，这可能很方便。

与 `get_tool_schemas` 类似，您可以传入 `api_format` 参数来指定工具模式的格式。

以下是 OpenAI Chat Completion 格式的示例：

```python
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="openai-chatcompletion" # 或 "openai"
) # 您可以省略 api_format，默认为 "openai-chatcompletion"
```

```json
[
  {
    "content": null,
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_wAcYzTLh37jfrCmihEv7x4FC",
        "function": {
          "arguments": "{\"a\":15,\"b\":3}",
          "name": "subtract"
        },
        "type": "function"
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_wAcYzTLh37jfrCmihEv7x4FC",
    "content": "12"
  }
]
