# 原生 Python 工具

ToolRegistry 支持直接注册 Python 函数和类——无需外部协议或适配器。

## 函数

最简单的工具创建方式。使用 `@registry.register` 或 `registry.register(func)`：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b

# 或显式注册
def multiply(x: float, y: float) -> float:
    """两数相乘。"""
    return x * y

registry.register(multiply)
```

类型标注自动生成 JSON Schema 参数。Docstring 作为工具描述。

完整教程请参阅[快速开始](../basics.md)和[函数调用](../function_calling.md)。

## 类

使用 `register_from_class()` 一次性注册 Python 类的所有方法。方法自动按类名分配命名空间。

```python
class MathTools:
    @staticmethod
    def add(a: int, b: int) -> int:
        """两数相加。"""
        return a + b

    @staticmethod
    def subtract(a: int, b: int) -> int:
        """a 减 b。"""
        return a - b

registry.register_from_class(MathTools)
# 注册: math-tools-add, math-tools-subtract
```

支持静态方法和实例方法。详细用法（实例类、构造参数、MRO 遍历）请参阅[基于类的工具](class.md)。
