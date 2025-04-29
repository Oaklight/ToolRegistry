# ToolRegistry

[中文版](README_zh.md)

A Python library for managing and executing tools in a structured way.

## Features

- Tool registration and management
- JSON Schema generation for tool parameters
- Tool execution and result handling
- Support for both synchronous and asynchronous tools
- Support [MCP sse](https://toolregistry.lab.oaklight.cn/mcp.html), [OpenAPI](https://toolregistry.lab.oaklight.cn/openapi.html) tools

## Full Documentation

Full documentation is available at [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## API Changes (starting 0.4.4)

Previously, the method `ToolRegistry.register_static_tools` was used for registering static methods from classes. This has now been replaced by `ToolRegistry.register_from_class`. Similarly, `ToolRegistry.register_mcp_tools` has been replaced by `ToolRegistry.register_from_mcp`, and `ToolRegistry.register_openapi_tools` by `ToolRegistry.register_from_openapi`. All old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, the old names remain as aliases to the new ones.

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

The ToolRegistry provides first-class support for MCP (Model Context Protocol) tools with multiple transport options:

```python
# Can be URL string, path to script, or transport instance
transport = "http://localhost:8000/sse"
transport = "examples/mcp_related/mcp_servers/math_server.py"

registry.register_from_mcp(transport)

# Get all tools JSON including MCP tools
tools_json = registry.get_tools_json()
```

Supported transport types:

- URL string (http://, https://, ws://, wss://)
- Path to script file (.py, .js)
- Existing ClientTransport instance
- FastMCPServer instance

## OpenAPI Integration

ToolRegistry supports integration with OpenAPI for interacting with tools using a standardized API interface:

```python
registry.register_from_openapi("http://localhost:8000/") # by providing baseurl
registry.register_from_openapi("./openapi_spec.json", "http://localhost/") # by providing local OpenAPI spec file and base url

# Get all tools JSON including OpenAPI tools
tools_json = registry.get_tools_json()
```

## Registering Hub Tools

Hub tools are registered to ToolRegistry using the `register_from_class` method. This allows developers to extend the functionality of ToolRegistry by creating custom tool classes with reusable methods.

Example:

```python
from toolregistry import ToolRegistry

class StaticExample:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hello, {name}!"

class InstanceExample:
    def __init__(self, name: str):
        self.name = name

    def greet(self, name: str) -> str:
        return f"Hello, {name}! I'm {self.name}."

registry = ToolRegistry()
registry.register_from_class(StaticExample, with_namespace=True)
print(registry.get_available_tools())  # ['static_example.greet']
print(registry["static_example.greet"]("Alice"))  # Hello, Alice!

registry = ToolRegistry()
registry.register_from_class(InstanceExample("Bob"), with_namespace=True)
print(registry.get_available_tools())  # ['instance_example.greet']
print(registry["instance_example.greet"]("Alice"))  # Hello, Alice! I'm Bob.
```

### Hub Tools

[Latest Available Tools](src/toolregistry/hub/)

Hub tools encapsulate commonly used functionalities as methods in classes. These tools are grouped for better organization and reusability.

Examples of available hub tools include:

- **Calculator**: Basic arithmetic, scientific operations, statistical functions, financial calculations, and more.
- **FileOps**: File manipulation operations like diff generation, patching, and verification.
- **Filesystem**: Comprehensive file system operations such as directory listing, file reading/writing, and path manipulation.
- **UnitConverter**: Extensive unit conversion tools for temperature, length, weight, and more.
- **WebSearch**: Web search functionality supporting multiple search engines including SearxNG and Google.

To register hub tools:

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_from_class(Calculator, with_namespace=True)

# Get available tools list
print(registry.get_available_tools())
# Output: ['Calculator.add', 'Calculator.subtract', ..., 'Calculator.multiply', ...]
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
