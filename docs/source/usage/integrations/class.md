# Class-based Tools Usage Guide

Hub tools are registered to ToolRegistry using the `register_from_class` method. This allows developers to extend the functionality of ToolRegistry by creating custom tool classes with reusable methods.

> **Note:** Previously, the method `register_static_tools` and the concept of `StaticMethodIntegration` were used for registering static methods from classes. These have now been replaced by `register_from_class`. Similarly, `register_static_tools_async` has also been replaced. Both old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, `register_static_tools` remains as an alias to `register_from_class`.

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

For predefined classes with pre-implemented functionalities (e.g., `Calculator`), registration is straightforward:

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_from_class(Calculator)  # Basic registration for methods of a class
```

These examples highlight how to manage varying needs for class-based registrations, allowing users to adapt `ToolRegistry` for diverse scenarios.

## `with_namespace` Option

Using `with_namespace=True` parameter adds the class name as a namespace prefix to tool names:

```python
registry.register_from_class(Calculator, with_namespace=True)
```

This will register tools with names like `Calculator.add`, `Calculator.subtract`, etc.

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
# Output: ['Calculator.add', 'Calculator.subtract', ..., 'read_file', 'write_file', ...]
