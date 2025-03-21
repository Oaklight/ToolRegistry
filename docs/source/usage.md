# Usage

This page explains how to set up and use the **ToolRegistry** library.

---

## Installation

### Prerequisites

Before setting up ToolRegistry, ensure you have the following installed:

- **Python 3.8+**
- **pip** (for dependency management)

### Installation

```bash
pip install toolregistry
```

### Installation from Source

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install .
```

---

## Basic Usage

### Registering Tools

```python
from tool_registry import ToolRegistry

# Create a registry instance
registry = ToolRegistry()

# Register a tool
@registry.register
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
```

### Executing Tools

```python
# Execute a registered tool
result = registry.execute_tool("add", {"a": 1, "b": 2})
print(result)  # Output: 3
```

### OpenAI Integration

```python
# Get tools JSON for OpenAI
tools_json = registry.get_tools_json()

# Execute tool calls from OpenAI
tool_responses = registry.execute_tool_calls(tool_calls)

# Recover assistant messages
messages = registry.recover_tool_call_assistant_message(tool_calls, tool_responses)
```

### Manual Tool Execution

```python
# Get a callable function
add_fn = registry.get_callable("add")
result = add_fn(a=1, b=2)  # Output: 3
```

---

## Advanced Usage

### Merging Registries

```python
registry1 = ToolRegistry()
registry2 = ToolRegistry()

# Merge registry2 into registry1
registry1.merge(registry2)
```

### Tool Parameter Schema

```python
# Get the JSON schema for a tool's parameters
tool_schema = registry.get_tools_json()[0]['function']['parameters']
```

---

## Best Practices

1. Use descriptive tool names and documentation
2. Keep tool functions focused on single responsibilities
3. Validate tool parameters before execution
4. Handle errors gracefully in tool implementations
5. Use type hints for better documentation and validation
