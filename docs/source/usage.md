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

## Implementation Examples

### Cicada Implementation

This example shows how to use ToolRegistry with the Cicada MultiModalModel:

```python
import os
from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from toolregistry import ToolRegistry

# Initialize Cicada model
model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

llm = MultiModalModel(
    api_key="your-api-key",
    api_base_url="https://api.deepseek.com/",
    model_name=model_name,
    stream=stream,
)

# Initialize ToolRegistry
tool_registry = ToolRegistry()

# Register tools
@tool_registry.register
def get_weather(location: str):
    return f"Weather in {location}: Sunny, 25°C"

@tool_registry.register
def c_to_f(celsius: float) -> float:
    fahrenheit = (celsius * 1.8) + 32
    return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"

# Query the model with tools
response = llm.query(
    "上海的气温如何，用华氏度回答我?",
    tools=tool_registry,
    stream=True,
)
print(response["content"])
```

### OpenAI Implementation

This example demonstrates integration with OpenAI's API:

```python
from openai import OpenAI
from toolregistry import ToolRegistry

# Initialize ToolRegistry
tool_registry = ToolRegistry()

# Register tools
@tool_registry.register
def get_weather(location: str):
    """Get the weather for a specific location"""
    return f"Weather in {location}: Sunny, 25°C"

@tool_registry.register
def c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit"""
    fahrenheit = (celsius * 1.8) + 32
    return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"

# Set up OpenAI client
client = OpenAI(
    api_key="your-api-key",
    base_url="https://api.deepseek.com/",
)

# Make chat completion request
messages = [{"role": "user", "content": "上海的气温如何，用华氏度回答我?"}]
response = client.chat.completions.create(
    model="deepseek-v3",
    messages=messages,
    tools=tool_registry.get_tools_json(),
    tool_choice="auto",
)

# Handle tool calls
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    tool_responses = tool_registry.execute_tool_calls(tool_calls)
    messages.extend(tool_registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses
    ))

    # Get final response
    second_response = client.chat.completions.create(
        model="deepseek-v3", messages=messages
    )
    print(second_response.choices[0].message.content)
```

## Best Practices

1. Use descriptive tool names and documentation
2. Keep tool functions focused on single responsibilities
3. Validate tool parameters before execution
4. Handle errors gracefully in tool implementations
5. Use type hints for better documentation and validation
