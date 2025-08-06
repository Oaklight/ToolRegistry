# Hub Tools Usage Guide

```{note}
New in version: 0.4.2
```

```{important}
**Hub Tools Package Update**: starting 0.4.14, hub tools have been moved to a separate package `toolregistry-hub`. You can install it via:

- `pip install toolregistry-hub` (standalone installation)
- `pip install toolregistry[hub]` (as an extra dependency)

Both methods provide the same functionality. The standalone installation allows you to use hub tools independently or with other compatible libraries.
```

## Introduction

Hub encapsulates commonly used tools as methods of a class, including both static methods and instance methods, serving as ready-to-use tool groups. This design offers several advantages:

1. **Organization**: Related tool methods are grouped in the same class for easier management and maintenance.
2. **Reusability**: Pre-built tools can be imported and used directly without reimplementation.
3. **Consistency**: All tools follow the same interface specification.
4. **Extensibility**: New tool classes or methods can be easily added.
5. **Safety and Exception Handling**: Encapsulated tools provide better control over security and handle exceptions more effectively compared to allowing models to directly execute commands.

Hub tools can be registered using the `register_from_class` method. Refer to [**Registering Class-Based Python Tools**](../class.md) for detailed instructions.

## Example of Using Predefined Tools

Hub also provides predefined classes with ready-to-use methods. These tools can be easily registered and used without additional setup.

```python
from toolregistry import ToolRegistry
from toolregistry.hub import BaseCalculator, Calculator, FileOps

# Create tool registry
registry = ToolRegistry()

# Register Calculator tools (with namespace)
registry.register_from_class(Calculator, with_namespace=True)

# Register FileOps tools (without namespace)
registry.register_from_class(FileOps)

# Get available tools list
print(registry.get_available_tools())
# Output: ['calculator-list_allowed_fns', 'calculator-help', 'calculator-evaluate', 'read_file', 'write_file', ...]
```

Using the `with_namespace=True` parameter during registration adds the class name as a namespace prefix to tool names, ensuring better organization and avoiding naming conflicts. For example:

```python
registry.register_from_class(BaseCalculator, with_namespace=True)
```

This will register tools with names like `base_calculator-add`, `base_calculator-subtract`, etc.

Advantages of using `with_namespace`:

1. Avoids naming conflicts between methods with the same names in different classes.
2. More clearly identifies tool sources.
3. Maintains naming consistency.
