# Usage Guide

```{toctree}
:hidden:
openai
mcp
openapi
examples
best_practices
```

This page covers the basic usage of registering tools, processing tool calls, and bridging a tool registry to the OpenAI API.
Let's use a simple math tool registry for demonstration purpose.

## Basic Use Cases

### Registering Tools

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

### Get and Access Available Tool Names

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

### JSON Schema of Tools

You can use the `get_tools_json` method **at ToolRegistry-level** to retrieve the tools' JSON schemas that are compatible with OpenAI's function calling interface.

```python
# Get tools JSON for OpenAI
tools_json = registry.get_tools_json()

print(tool_json)
```

You will see the following. Meanwhile, you can see the difference of parameter `a`'s `type` in function `add` and `subtract`, one as `number`, another as `integer`.

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
      "is_async": false
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
      "is_async": false
    }
  }
]
```

If you are interested in **Tool-level** JSON schema, then you can use `get_json_schema` (or `describe`, actually this is an alias to `get_json_schema`)

```python
add_tool.get_json_schema()
add_tool.describe() # simpler interface
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
    },
    "is_async": true
  }
}
```

### Executing Tools

```python
# Execute tool calls (tool_calls comes from OpenAI's API response)
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
print(tool_responses[0].result)  # Output: 3
```

Please read [OpenAI Function Calling](openai) for detailed example and step-by-step breakdown with explanation.

### Manual Tool Execution

```python
# Get a callable function
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # Output: 3
```

---

## Advanced Usage

### Merging Registries

Merging registries allows you to combine tools from multiple registries into one. During the merge process, the `registry name` is used as a prefix (namespace) to clearly distinguish tools from different registries. This ensures that tools are organized and managed effectively.

We recommend organizing tools by similar functionality to form a registry. The `merge` function is intended to centralize multiple registries (functional groups) for convenient presentation to the LLM.

```python
# Example of MCP/OpenAPI mixed registry
openapi_registry = ToolRegistry("openapi_math")
mcp_registry = ToolRegistry("mcp_math")

# Merge MCP registry into OpenAPI registry
mixed_registry = openapi_registry
mixed_registry.merge(mcp_registry)

print(mixed_registry.get_available_tools())  # Tools from both registries
```

```python
 ['openapi_math.add_get', 'openapi_math.subtract_get', 'openapi_math.multiply_get', 'openapi_math.divide_get', 'mcp_math.add', 'mcp_math.subtract', 'mcp_math.multiply', 'mcp_math.divide']
```

### Spinoff Registries

Spinoff registries allow you to extract tools with specific prefixes from an existing registry, typically after a merge operation. During the spinoff process, the prefix is removed from the extracted tools. If the remaining tools in the registry share only one prefix, they will also be downgraded by removing the prefix. This is useful for reorganizing tools or creating specialized registries.

```python
# Example from MCP/OpenAPI mixed registry
openapi_registry2 = mixed_registry.spinoff("openapi_math")

print(openapi_registry2.get_available_tools())  # Tools from openapi registry
print(mixed_registry.get_available_tools())  # Tools with mcp registry
```

```python
['add_get', 'subtract_get', 'multiply_get', 'divide_get']
['add', 'subtract', 'multiply', 'divide']
```

### Tool Parameter Schema

```python
# Get the JSON schema for a tool's parameters
tool_params_schema = registry.get_tools_json("subtract")[0]['function']['parameters']
print(tool_params_schema)
```

```json
{
  "properties": {
    "a": { "title": "A", "type": "integer" },
    "b": { "title": "B", "type": "integer" }
  },
  "required": ["a", "b"],
  "title": "subtractParameters",
  "type": "object"
}
```
