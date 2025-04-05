# ToolRegistry

[中文版](README_zh.md)

A Python library for managing and executing tools in a structured way.

## Features

- Tool registration and management
- JSON Schema generation for tool parameters
- Tool execution and result handling
- Support for both synchronous and asynchronous tools
- Support [MCP sse](https://toolregistry.lab.oaklight.cn/mcp.html), [OpenAPI](https://toolregistry.lab.oaklight.cn/openapi.html) tools

## Installation

### Basic Installation

Install the core package (requires **Python >= 3.8**):

```bash
pip install toolregistry
```

### Installing with Extra Support Modules

Extra modules can be installed by specifying extras in brackets. For example, to install specific extra supports:

```bash
pip install toolregistry[mcp,openapi]
```

Below is a table summarizing available extra modules:

| Extra Module | Python Requirement | Example Command                   |
| ------------ | ------------------ | --------------------------------- |
| mcp          | Python >= 3.10     | pip install toolregistry[mcp]     |
| openapi      | Python >= 3.8      | pip install toolregistry[openapi] |

## Examples

### OpenAI Implementation

The [openai_tool_usage_example.py](examples/openai_tool_usage_example.py) shows how to integrate ToolRegistry with OpenAI's API.

### Cicada Implementation

The [cicada_tool_usage_example.py](examples/cicada_tool_usage_example.py) demonstrates how to use ToolRegistry with the Cicada MultiModalModel.

## Basic Tool Invocation

This section demonstrates how to invoke a basic tool. Example:

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

available_tools = registry.get_available_tools()

print(available_tools) # ['add']

add_func = registry.get_callable('add')
print(type(add_func)) # <class 'function'>
add_result = add_func(1, 2)
print(add_result) # 3

add_func = registry['add']
print(type(add_func)) # <class 'function'>
add_result = add_func(4, 5)
print(add_result) # 9
```

For more usage examples, please refer to [Documentation - Usage](https://toolregistry.lab.oaklight.cn/usage.html)

## MCP Integration

The ToolRegistry provides first-class support for MCP (Model Context Protocol) tools:

```python
registry.register_mcp_tools("http://localhost:8000/mcp/sse")

# Get all tools JSON including MCP tools
tools_json = registry.get_tools_json()
```

## OpenAPI Integration

ToolRegistry supports integration with OpenAPI for interacting with tools using a standardized API interface:

```python
registry.register_openapi_tools("http://localhost:8000/") # by providing baseurl
registry.register_openapi_tools("./openapi_spec.json", "http://localhost/") # by providing local OpenAPI spec file and base url

# Get all tools JSON including OpenAPI tools
tools_json = registry.get_tools_json()
```

## Documentation

Full documentation is available at [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
