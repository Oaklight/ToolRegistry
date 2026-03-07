# Class-based Tools Usage Guide

Hub tools are registered to ToolRegistry using the `register_from_class` method. This allows developers to extend the functionality of ToolRegistry by creating custom tool classes with reusable methods.

???+ note "API changes"
    Previously (before 0.4.12), the method `register_static_tools` and the concept of `StaticMethodIntegration` were used for registering static methods from classes. These have now been replaced by `register_from_class`. Similarly, `register_static_tools_async` has also been replaced. Both old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, `register_static_tools` remains as an alias to `register_from_class`.

## Registering Custom Class Methods

The `register_from_class` method in `ToolRegistry` allows you to easily register methods from custom classes, whether they are static methods or instance methods. Below, we explore two distinct use cases: registering classes with only static methods and registering instance-based classes.

### Registering a Class with Static Methods

Classes that exclusively use static methods can be registered directly without creating instances. Use the `with_namespace=True` argument to help organize tools under a namespace derived from the class name.

```python
from toolregistry import ToolRegistry

class StaticExample:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hello, {name}!"

registry = ToolRegistry()
registry.register_from_class(StaticExample, with_namespace=True)

# List registered tools
print(registry.get_available_tools())
# Output: ['static_example.greet']

# Call a registered tool
print(registry["static_example.greet"]("Alice"))  # Hello, Alice!
```

### Registering a Class with Instance Methods

For classes utilizing instance methods, you need to create an instance and pass it to the registry along with the class definition. This ensures that the methods have access to instance-specific data.

```python
from toolregistry import ToolRegistry

class InstanceExample:
    def __init__(self, name: str):
        self.name = name

    def greet(self, name: str) -> str:
        return f"Hello, {name}! I'm {self.name}."

# Creating an instance of the class
example_instance = InstanceExample("Bob")
registry = ToolRegistry()

# Register methods using the instance
registry.register_from_class(InstanceExample, instance=example_instance)

# List registered tools
print(registry.get_available_tools())
# Output: ['instance_example.greet']

# Call a registered tool
print(registry["instance_example.greet"]("Alice"))  # Hello, Alice! I'm Bob.
```

### Additional Example: A Predefined Class from a Tool Hub

For predefined classes with pre-implemented functionalities (e.g., `BaseCalculator`, `Calculator`), registration is straightforward:

```python
from toolregistry import ToolRegistry
from toolregistry.hub import BaseCalculator

registry = ToolRegistry()
registry.register_from_class(BaseCalculator)  # Basic registration for methods of a class
```

These examples highlight how to manage varying needs for class-based registrations, allowing users to adapt `ToolRegistry` for diverse scenarios.

### Registering Inherited Methods with `traverse_mro`

By default, `register_from_class()` only registers methods defined directly on the given class. If you want to also include methods inherited from parent classes, use the `traverse_mro=True` parameter:

```python
from toolregistry import ToolRegistry

class BaseCalculator:
    @staticmethod
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    @staticmethod
    def subtract(a: int, b: int) -> int:
        """Subtract two numbers."""
        return a - b

class ScientificCalculator(BaseCalculator):
    @staticmethod
    def power(base: float, exp: float) -> float:
        """Raise base to the power of exp."""
        return base ** exp

registry = ToolRegistry()

# Without traverse_mro (default): only 'power' is registered
registry.register_from_class(ScientificCalculator, with_namespace=True)
print(registry.get_available_tools())
# Output: ['scientific_calculator-power']

# With traverse_mro=True: inherited methods 'add' and 'subtract' are also registered
registry2 = ToolRegistry()
registry2.register_from_class(ScientificCalculator, with_namespace=True, traverse_mro=True)
print(registry2.get_available_tools())
# Output: ['scientific_calculator-add', 'scientific_calculator-subtract', 'scientific_calculator-power']
```

This is useful when you have a class hierarchy and want to expose all available methods (including inherited ones) as tools.

## `with_namespace` Option

Using `with_namespace=True` parameter adds the class name as a namespace prefix to tool names:

```python
registry.register_from_class(BaseCalculator, with_namespace=True)
```

This will register tools with names like `base_calculator-add`, `base_calculator-subtract`, etc.

**Advantages of using with_namespace**:

1. Avoids naming conflicts between methods with same names in different classes
2. More clearly identifies tool source
3. Maintains naming consistency

## Example Code

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator, FileOps

# Create tool registry
registry = ToolRegistry()

# Register Calculator tools (with namespace)
registry.register_from_class(Calculator, with_namespace=True)

# Register FileOps tools (without namespace)
registry.register_from_class(FileOps)

# Get available tools list
print(registry.get_available_tools())
# Output: ['calculator-list_allowed_fns', 'calculator-help', 'calculator-evaluate', 'read_file', 'write_file', ...]
