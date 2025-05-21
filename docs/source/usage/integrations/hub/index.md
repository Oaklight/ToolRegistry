# Hub Tools and Static Method Integration

```{tip}
New in version: 0.4.2
```

```{note}
Starting from version 0.4.4, several API methods have been updated for better consistency and usability:

- `ToolRegistry.register_static_tools` has been replaced by `ToolRegistry.register_from_class`.
- `ToolRegistry.register_mcp_tools` has been replaced by `ToolRegistry.register_from_mcp`.
- `ToolRegistry.register_openapi_tools` has been replaced by `ToolRegistry.register_from_openapi`.

The old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, the old names remain as aliases to the new ones.
```

## Introduction

Hub encapsulates commonly used tools as methods of a class, including both static methods and instance methods, serving as ready-to-use tool groups. This design offers several advantages:

1. **Organization**: Related tool methods are grouped in the same class for easier management and maintenance
2. **Reusability**: Pre-built tools can be imported and used directly without reimplementation
3. **Consistency**: All tools follow the same interface specification
4. **Extensibility**: New tool classes or methods can be easily added
5. **Safety and Exception Handling**: Encapsulated tools provide better control over security and handle exceptions more effectively compared to allowing models to directly execute commands.

## Currently Available Hub Tools

For latest list of predefined tools, please check out [**latest available**](https://github.com/Oaklight/ToolRegistry/tree/master/src/toolregistry/hub)

```{toctree}
:caption: Available Hub Tools

t_calculator
t_fileops
t_filesystem
t_unit_converter
t_websearch
```

## Registering Hub Tools

Hub tools are registered to ToolRegistry using the `register_from_class` method. This allows developers to extend the functionality of ToolRegistry by creating custom tool classes with reusable methods.

> **Note:** Previously, the method `register_static_tools` and the concept of `StaticMethodIntegration` were used for registering static methods from classes. These have now been replaced by `register_from_class`. Similarly, `register_static_tools_async` has also been replaced. Both old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, `register_static_tools` remains as an alias to `register_from_class`.

### Registering Custom Class Methods

To register methods from a custom class, simply use the `register_from_class` method:

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

# List registered tools
print(registry.get_available_tools())
# Output: ['static_example.greet']

# Call a registered tool
print(registry["static_example.greet"]("Alice"))  # Hello, Alice!
```

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_from_class(Calculator)  # Basic registration for methods of a class
```

### `with_namespace` Option

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
```
