# Native Python Tools

ToolRegistry supports registering plain Python functions and classes directly — no external protocols or adapters required.

## Functions

The simplest way to create tools. Use `@registry.register` or `registry.register(func)`:

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

# Or register explicitly
def multiply(x: float, y: float) -> float:
    """Multiply two numbers."""
    return x * y

registry.register(multiply)
```

Type annotations are used to generate JSON Schema parameters automatically. Docstrings become tool descriptions.

For a complete walkthrough including schema generation and LLM integration, see [Quick Start](../basics.md) and [Function Calling](../function_calling.md).

## Classes

Register all methods from a Python class at once using `register_from_class()`. Methods are automatically namespaced by class name.

```python
class MathTools:
    @staticmethod
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @staticmethod
    def subtract(a: int, b: int) -> int:
        """Subtract b from a."""
        return a - b

registry.register_from_class(MathTools)
# Registers: math-tools-add, math-tools-subtract
```

Both static methods and instance methods are supported. For detailed usage including instance classes, constructor arguments, and MRO traversal, see [Class-based Tools](class.md).
