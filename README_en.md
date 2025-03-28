# ToolRegistry

[中文版](README_zh.md)

A Python library for managing and executing tools in a structured way.

## Features

- Tool registration and management
- JSON Schema generation for tool parameters
- Tool execution and result handling
- Support for both synchronous and asynchronous tools

## Installation

```bash
pip install toolregistry
```

## Examples

### OpenAI Implementation

The [openai_tool_usage_example.py](examples/openai_tool_usage_example.py) shows how to integrate ToolRegistry with OpenAI's API.

### Cicada Implementation

The [cicada_tool_usage_example.py](examples/cicada_tool_usage_example.py) demonstrates how to use ToolRegistry with the Cicada MultiModalModel.

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

Full documentation is available at [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
