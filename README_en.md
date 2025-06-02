# ToolRegistry

[English Version](README_en.md) | [中文版](README_zh.md)

A Python library for managing and executing tools in a structured way.

## Features

- Tool registration and management
- JSON Schema generation for tool parameters
- Tool execution and result handling
- Support for both synchronous and asynchronous tools
- Support native Python functions and class methods as tools
- Support multiple [MCP](https://toolregistry.lab.oaklight.cn/mcp.html) transport methods: STDIO, streamable HTTP, SSE, WebSocket, FastMCP instance, etc.
- Support [OpenAPI](https://toolregistry.lab.oaklight.cn/openapi.html) tools

## Full Documentation

Full documentation is available at [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## API Deprecation (starting 0.4.12)

As of version 0.4.12, the previously deprecated methods `ToolRegistry.register_static_tools`, `ToolRegistry.register_mcp_tools`, and `ToolRegistry.register_openapi_tools` have been **REMOVED**. Users must update their implementations to use the new methods: `ToolRegistry.register_from_class`, `ToolRegistry.register_from_mcp`, and `ToolRegistry.register_from_openapi`. Please ensure your codebase is compatible with this update for uninterrupted functionality.

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

| Extra Module | Python Requirement | Example Command                     |
| ------------ | ------------------ | ----------------------------------- |
| mcp          | Python >= 3.10     | pip install toolregistry[mcp]       |
| openapi      | Python >= 3.8      | pip install toolregistry[openapi]   |
| langchain    | Python >= 3.9      | pip install toolregistry[langchain] |

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
# transport can be a URL string, script path, transport instance, or MCP instance.
transport = "https://mcphub.url/mcp"  # Streamable HTTP MCP
transport = "http://localhost:8000/sse/test_group"  # Legacy HTTP+SSE
transport = "examples/mcp_related/mcp_servers/math_server.py"  # Local path
transport = {
    "mcpServers": {
        "make_mcp": {
            "command": f"{Path.home()}/mambaforge/envs/toolregistry_dev/bin/python",
            "args": [
                f"{Path.home()}/projects/toolregistry/examples/mcp_related/mcp_servers/math_server.py"
            ],
            "env": {},
        }
    }
}  # MCP configuration dictionary example
transport = FastMCP(name="MyFastMCP")  # FastMCP instance
transport = StreamableHttpTransport(url="https://mcphub.example.com/mcp", headers={"Authorization": "Bearer token"})  # Transport instance with custom headers

registry.register_from_mcp(transport)

# Get all tools' JSON, including MCP tools
tools_json = registry.get_tools_json()
```

## OpenAPI Integration (updated as of 0.4.12)

The `register_from_openapi` method now accepts two parameters:

- `client_config`: a `toolregistry.openapi.HttpxClientConfig` object that configures the HTTP client used to interact with the API. You can configure the headers, authorization, timeout, and other settings. Allowing greater flexibility than the previous version.
- `openapi_spec`: The OpenAPI specification as `Dict[str, Any]`, loaded with a function like `load_openapi_spec` or `load_openapi_spec_async`. These functions accept a file path or a URL to the OpenAPI specification or a URL to the base api and return the parsed OpenAPI specification as a dictionary.

Example:

```python
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec

client_config = HttpxClientConfig(base_url="http://localhost:8000")
openapi_spec = load_openapi_spec("./openapi_spec.json")
openapi_spec = load_openapi_spec("http://localhost:8000")
openapi_spec = load_openapi_spec("http://localhost:8000/openapi.json")

registry.register_from_openapi(
    client_config=client_config,
    openapi_spec=openapi_spec
)

# Get all tools' JSON, including OpenAPI tools
tools_json = registry.get_tools_json()
```

### Note

When using the functions `load_openapi_spec` or `load_openapi_spec_async`, the following behaviors apply:

1. **Base URL provided**: If you specify only a base URL (e.g., `http://localhost:8000`), the loader will attempt "best effort" auto-discovery to locate the OpenAPI specification file. It checks endpoints such as `http://<base_url>/openapi.json` or `http://<base_url>/swagger.json`. If auto-discovery fails, ensure the base URL is accurate and the specification is accessible.

2. **File path provided**: If you provide a file path (e.g., `./openapi_spec.json`), the function will load the OpenAPI specification directly from the file. Unlike simple direct load, the functionality includes unwinding `$ref` blocks commonly found in OpenAPI specifications. This ensures that any schema references are fully resolved within the returned dictionary.

## LangChain Integration

The LangChain integration module allows ToolRegistry to register and invoke LangChain tools seamlessly, supporting both synchronous and asynchronous calls.

```python
from langchain_community.tools import ArxivQueryRun, PubmedQueryRun
from toolregistry import ToolRegistry

registry = ToolRegistry()

registry.register_from_langchain([ArxivQueryRun(), PubmedQueryRun()])
tools_json = registry.get_tools_json()
```

## Registering Class Tools

Class tools are registered to ToolRegistry using the `register_from_class` method. This allows developers to extend the functionality of ToolRegistry by creating custom tool classes with reusable methods.

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

[Available Tools](src/toolregistry/hub/)

Hub tools encapsulate commonly used functionalities as methods in classes. Examples of available hub tools include:

- **Calculator**: Basic arithmetic, scientific operations, statistical functions, financial calculations, and more.
- **FileOps**: File manipulation like diff generation, patching, verification, merging, and splitting.
- **Filesystem**: Comprehensive file system operations such as directory listing, file read/write, path normalization, and querying file attributes.
- **UnitConverter**: Extensive unit conversions such as temperature, length, weight, volume, etc.
- **WebSearch**: Web search functionality supporting multiple engines like Bing, Google and SearXNG, etc.
- **Fetch**: Fetching content from URL.

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

### Community Contribution

We welcome community contributions of new tool classes to ToolRegistry! If you have designs or implementations for other commonly used tools, feel free to submit them through a Pull Request on the [GitHub Repository](https://github.com/yourrepository/toolregistry). Your contributions will help expand the diversity and usability of the tools.

## Citation

If you use ToolRegistry in your research or project, please consider cite it as:

```bibtex
@software{toolregistry2025,
  title={ToolRegistry: A Protocol-Agnostic Tool Management Library for OpenAI-Compatible LLM Applications},
  author={Peng Ding},
  year={2025},
  url={https://github.com/Oaklight/ToolRegistry},
  note={A Python library for unified tool registration, execution, and management across multiple protocols in OpenAI-compatible LLM applications}
}
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
