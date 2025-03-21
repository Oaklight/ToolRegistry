# Tool Registry Library

A Python library for managing and executing tools in a structured way.

## Features

- Tool registration and management
- JSON Schema generation for tool parameters
- Tool execution and result handling
- Support for both synchronous and asynchronous tools

## Installation

```bash
pip install tool-registry-lib
```

## Usage

```python
from tool_registry import ToolRegistry

# Create a registry instance
registry = ToolRegistry()

# Register a tool
@registry.register
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# Execute a tool
result = registry.execute_tool("add", {"a": 1, "b": 2})
print(result)  # Output: 3
```

## OpenAI Integration

The ToolRegistry integrates seamlessly with OpenAI's API. Here are some common usage patterns:

### Getting Tools JSON for OpenAI

```python
tools_json = registry.get_tools_json()
# Use this with OpenAI's API to provide available tools
```

### Executing Tool Calls

```python
# Assuming tool_calls is received from OpenAI's API
tool_responses = registry.execute_tool_calls(tool_calls)
```

### Recovering Assistant Messages

```python
# After executing tool calls
messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
# Use these messages to continue the conversation
```

### Manual Tool Execution

```python
# Get a callable function
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # Output: 3
```

## Documentation

Full documentation is available at [https://github.com/Oaklight/ToolRegistry](https://github.com/Oaklight/ToolRegistry)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
