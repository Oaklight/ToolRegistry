# 函数工具

将 Python 函数注册为工具——ToolRegistry 中最常见、最简单的工具创建方式。

## 装饰器注册

使用 `@registry.register` 直接注册函数：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b
```

## 显式注册

通过编程方式注册函数，可选覆盖名称和描述：

```python
def multiply(x: float, y: float) -> float:
    """两数相乘。"""
    return x * y

registry.register(multiply)

# 自定义名称和描述
registry.register(multiply, name="mul", description="x 乘以 y")
```

## 工作原理

- **类型标注** → JSON Schema 参数（例如 `a: int` 变为 `{"type": "integer"}`）
- **Docstring** → 提供给 LLM 的工具描述
- **返回类型** → 不包含在 schema 中，但用于文档
- **默认值** → 反映在 schema 中，参数变为可选

```python
def search(query: str, max_results: int = 10) -> list:
    """搜索匹配查询的项目。

    Args:
        query: 搜索词。
        max_results: 返回的最大结果数。
    """
    ...
```

生成的 schema 中 `query` 为必填参数，`max_results` 为可选参数，默认值为 `10`。

## 命名空间

使用 `namespace` 参数对相关函数进行分组：

```python
registry.register(add, namespace="math")
registry.register(subtract, namespace="math")
# 注册为: math-add, math-subtract
```

详见[命名空间指南](../namespace.md)。

## Tool 实例

也可以注册预构建的 `Tool` 对象：

```python
from toolregistry import Tool

tool = Tool.from_function(add, description="自定义描述")
registry.register(tool)
```

## 下一步

- [函数调用](../function_calling.md) — 与 LLM API 的端到端教程
- [基于类的工具](class.md) — 一次性注册 Python 类的所有方法
- [最佳实践](../best_practices.md) — 编写优质工具函数的建议
