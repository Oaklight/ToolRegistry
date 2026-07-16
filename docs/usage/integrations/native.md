# Function Tools

Register plain Python functions as tools — the most common and simplest way to create tools in ToolRegistry.

## Decorator Registration

Use `@registry.register` to register a function directly:

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
```

## Explicit Registration

Register functions programmatically with optional name and description overrides:

```python
def multiply(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y

registry.register(multiply)

# With custom name and description
registry.register(multiply, name="mul", description="Multiply x by y")
```

## How It Works

- **Type annotations** → JSON Schema parameters (e.g. `a: int` becomes `{"type": "integer"}`)
- **Docstrings** → tool description for the LLM
- **Return type** → not included in schema, but used for documentation
- **Default values** → reflected in schema, parameter becomes optional

```python
def search(query: str, max_results: int = 10) -> list:
    """Search for items matching the query.

    Args:
        query: The search term.
        max_results: Maximum number of results to return.
    """
    ...
```

This generates a schema where `query` is required and `max_results` is optional with default `10`.

## Namespaces

Use the `namespace` parameter to group related functions:

```python
registry.register(add, namespace="math")
registry.register(subtract, namespace="math")
# Registers: math-add, math-subtract
```

See [Namespace Guide](../namespace.md) for details.

## Tool Instances

You can also register pre-built `Tool` objects:

```python
from toolregistry import Tool

tool = Tool.from_function(add, description="Custom description")
registry.register(tool)
```

## What's Next

- [Function Calling](../function_calling.md) — end-to-end walkthrough with an LLM API
- [Class-based Tools](class.md) — register all methods from a Python class at once
- [Best Practices](../best_practices.md) — tips for writing good tool functions
