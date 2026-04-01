# 基于类的工具使用指南

Hub 工具通过 `register_from_class` 方法注册到 ToolRegistry 中。开发者可以通过创建包含可复用方法的自定义工具类来扩展 ToolRegistry 的功能。

???+ note "API 变更"
    在此前版本（0.4.12 之前），注册类的静态方法使用的是 `register_static_tools` 方法和 `StaticMethodIntegration` 概念。现在它们已被 `register_from_class` 取代。同样，`register_static_tools_async` 也已被替换。两个旧方法计划很快废弃，请尽快迁移至新接口。为了向后兼容，`register_static_tools` 仍作为 `register_from_class` 的别名保留。

## 注册自定义类方法

`ToolRegistry` 中的 `register_from_class` 方法允许你轻松注册自定义类中的方法，无论是静态方法还是实例方法。下面我们将分别介绍两种不同的使用场景：注册仅包含静态方法的类和注册基于实例的类。

### 注册包含静态方法的类

仅使用静态方法的类可以直接注册，无需创建实例。使用 `namespace=True` 参数可以帮助将工具组织到以类名派生的命名空间下。

```python
from toolregistry import ToolRegistry

class StaticExample:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hello, {name}!"

registry = ToolRegistry()
registry.register_from_class(StaticExample, namespace=True)

# List registered tools
print(registry.get_available_tools())
# Output: ['static_example.greet']

# Call a registered tool
print(registry["static_example.greet"]("Alice"))  # Hello, Alice!
```

### 注册包含实例方法的类

对于使用实例方法的类，你需要创建一个实例并将其与类定义一起传递给注册器。这样可以确保方法能够访问实例特有的数据。

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

### 附加示例：来自工具 Hub 的预定义类

对于具有预实现功能的预定义类（例如 `BaseCalculator`、`Calculator`），注册非常简单：

```python
from toolregistry import ToolRegistry
from toolregistry.hub import BaseCalculator

registry = ToolRegistry()
registry.register_from_class(BaseCalculator)  # Basic registration for methods of a class
```

这些示例展示了如何管理不同的基于类的注册需求，使用户能够在多种场景下灵活使用 `ToolRegistry`。

### 使用 `traverse_mro` 注册继承方法

默认情况下，`register_from_class()` 会遍历 MRO（方法解析顺序），同时注册直接定义的方法和继承的方法。这意味着父类中的继承公共方法会被自动包含在内。

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

# Default behavior (traverse_mro=True): inherited methods are included
registry.register_from_class(ScientificCalculator, namespace=True)
print(registry.get_available_tools())
# Output: ['scientific_calculator-add', 'scientific_calculator-subtract', 'scientific_calculator-power']

# With traverse_mro=False: only methods defined directly on the class are registered
registry2 = ToolRegistry()
registry2.register_from_class(ScientificCalculator, namespace=True, traverse_mro=False)
print(registry2.get_available_tools())
# Output: ['scientific_calculator-power']
```

如果你希望仅注册直接定义在该类上的方法（不包括继承的方法），请显式传递 `traverse_mro=False`。

## `namespace` 选项

使用 `namespace=True` 参数会将类名作为命名空间前缀添加到工具名称中：

```python
registry.register_from_class(BaseCalculator, namespace=True)
```

这将注册名称类似 `base_calculator-add`、`base_calculator-subtract` 等的工具。

**使用 namespace 的优势**：

1. 避免不同类中同名方法之间的命名冲突
2. 更清晰地标识工具来源
3. 保持命名一致性

## 示例代码

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator, FileOps

# Create tool registry
registry = ToolRegistry()

# Register Calculator tools (with namespace)
registry.register_from_class(Calculator, namespace=True)

# Register FileOps tools (without namespace)
registry.register_from_class(FileOps)

# Get available tools list
print(registry.get_available_tools())
# Output: ['calculator-list_allowed_fns', 'calculator-help', 'calculator-evaluate', 'read_file', 'write_file', ...]
```
