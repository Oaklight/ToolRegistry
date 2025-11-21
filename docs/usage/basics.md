# Basic Usage

This page covers the basic usage of registering tools, processing tool calls, and bridging a tool registry to the OpenAI API.
Let's use a simple math tool registry for demonstration purpose.

## Registering Tools

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@registry.register
def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first."""
    return a - b
```

## Access Available Tool Names

You can access the list of available tools by calling the `get_available_tools()` function:

```python
available_tools = registry.get_available_tools()

print(available_tools) # ['add', 'subtract']
```

You can access the available tools in the following ways:

1. as a Python `Callable`

   You can do it explicitly via `get_callable`

   ```python
   add_func = registry.get_callable('add')
   print(type(add_func)) # <class 'function'>

   add_result = add_func(1, 2)
   print(add_result) # 3
   ```

   You can also access via `__getitem__` method

   ```python
   add_func = registry['add']
   print(type(add_func)) # <class 'function'>

   add_result = add_func(4, 5)
   print(add_result) # 9
   ```

2. as a `toolregistry.tool.Tool`

   Use `get_tool` to explicitly expose the Tool interface.

   ```python
   add_tool = registry.get_tool("add")
   print(type(add_tool)) # <class 'toolregistry.tool.Tool'>

   value = add_tool.run({"a": 7, "b": 8})
   print(value) # 15.0
   ```

   Note that the result is 15.0 instead of 15 because the `add` function's type hints specify both `a` and `b` as floats. During schema validation in `toolregistry.tool.Tool`, integer inputs are converted to floats (7.0 and 8.0), resulting in a float output.

## JSON Schema of Tools

Use the `get_tools_json` method at the ToolRegistry level to retrieve JSON schemas compatible with your target API’s function calling interface.

We use each API standard’s function calling interface to handle integration, as function calling is the common, core feature enabling tool usage in every standard.

```python
# Get tools JSON for OpenAI
tools_json = registry.get_tools_json(api_format="openai-chatcompletion")
```

Since v0.4.13, we added a new parameter `api_format` to `get_tools_json` method, which is used to specify the API format of the tools JSON.

api_format can be one of the following, more will be added in the future:

- [x] `openai-chatcompletion` or `openai` (default)
- [x] `openai-response` (since v0.4.13)
- [ ] `anthropic` (WIP)
- [ ] `gemini` (WIP)

For example of `openai-chatcompletion`, you will see the following. Meanwhile, you can see the difference of parameter `a`'s `type` in function `add` and `subtract`, one as `number`, another as `integer`.

```json
[
  {
    "type": "function",
    "function": {
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
      "description": "Subtract the second number from the first.",
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

If you are interested in **Tool-level** JSON schema, you can use either of the following methods:

```python
registry.get_tools_json(tool_name="add", api_format="openai-chatcompletion") # you will need to specify the tool name
add_tool.get_json_schema(api_format="openai-chatcompletion")
add_tool.describe(api_format="openai-chatcompletion") # simpler interface, alias to get_json_schema
```

```json
{
  "type": "function",
  "function": {
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
      "required": ["a", "b"],
      "title": "addParameters",
      "type": "object"
    }
  }
}
```

## Executing Tools

After obtain the tool calls instructions from LLM response, you can execute them using the `execute_tool_calls` method of the `ToolRegistry` class. This method takes a list of tool calls and returns a list of tool response. Each tool response contains the result of the tool execution and other metadata.

```python
# tool_calls comes from LLMAPI response. Here is a mock example for OpenAI Chat Completion API.
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

By default the `execution_mode` parameter is set to `process`, which means the tool calls will be executed in parallel using multiple processes. For more information about the `execution_mode` parameter, please refer to the [Concurrency Modes: Thread Mode and Process Mode](concurrency_modes) section.

Results will be packed as a dictionary with the tool call ID as the key and the result as the value.

Please read [OpenAI Chat Completion Integration](providers/openai_chat) or specific provider integration guide for detailed example and step-by-step breakdown with explanation.

### Manual Tool Execution

You can also manually execute a tool by getting its callable function from the registry.

```python
# Get a callable function
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # Output: 3
```

## Reconstructing Assistant and Tool Calls Messages

The `ToolRegistry` class provides `recover_tool_call_assistant_message` to reconstruct assistant and tool calls messages for LLMs. This could be handy if you want to streamline the process of sending messages to LLMs.

Similar to `get_tool_schemas`, you can pass in the `api_format` parameter to specify the format of the tool schemas.

Here is an example of OpenAI Chat Completion format:

```python
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="openai-chatcompletion" # or "openai"
) # you can leave out api_format, it defaults to "openai-chatcompletion"
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
```
