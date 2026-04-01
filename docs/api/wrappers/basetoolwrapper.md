# BaseToolWrapper

ToolRegistry 生态系统中工具包装器的基类，提供同步和异步调用支持。

## 概览

`BaseToolWrapper` 作为 ToolRegistry 系统中所有工具包装器的基础抽象基类。它为工具执行提供了标准化接口，具备同步和异步能力，确保在不同工具类型和集成框架之间保持一致的行为。

## 主要特性

- **抽象接口**：定义工具执行的核心契约
- **双执行模式**：支持同步和异步工具执行
- **自动模式检测**：根据运行时上下文自动选择适当的执行模式
- **参数处理**：内置位置参数和关键字参数处理
- **标准化元数据**：一致的工具名称和参数列表处理

## 架构

BaseToolWrapper 遵循模板方法模式，具有以下设计：

### 抽象方法

1. **call_sync()**：子类必须实现，用于同步执行
2. **call_async()**：子类必须实现，用于异步执行

### 具体方法

1. \***\*call**()\*\*：自动在同步和异步执行之间选择
2. **\_process_args()**：处理和验证位置参数与关键字参数

### 执行流程

```
用户调用 wrapper()
    ↓
自动检测执行上下文
    ↓
调用 call_sync() 或 call_async()
    ↓
执行底层工具逻辑
    ↓
返回结果
```

## API 参考

::: toolregistry.tool_wrapper.BaseToolWrapper
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 使用示例

### 基本包装器实现

```python
from toolregistry.tool_wrapper import BaseToolWrapper
from typing import Any, List, Optional

class CustomToolWrapper(BaseToolWrapper):
    def __init__(self, name: str, tool_function: callable, params: Optional[List[str]] = None):
        super().__init__(name=name, params=params)
        self.tool_function = tool_function

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous tool execution."""
        processed_kwargs = self._process_args(*args, **kwargs)
        return self.tool_function(**processed_kwargs)

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronous tool execution."""
        processed_kwargs = self._process_args(*args, **kwargs)
        # Assuming tool_function supports async execution
        return await self.tool_function(**processed_kwargs)
```

### 自定义工具的使用

```python
def my_calculator(a: int, b: int) -> int:
    """Simple calculator function."""
    return a + b

# Create wrapper
wrapper = CustomToolWrapper(
    name="calculator",
    tool_function=my_calculator,
    params=["a", "b"]
)

# Automatic mode selection
result1 = wrapper(a=5, b=3)  # Sync execution
result2 = await wrapper(a=5, b=3)  # Async execution
```

## 参数处理

BaseToolWrapper 提供了完善的参数处理机制：

### 参数验证

```python
# Positional arguments are mapped to parameter names
wrapper = BaseToolWrapper("test", params=["param1", "param2"])

# These calls are equivalent:
wrapper("value1", "value2")
wrapper(param1="value1", param2="value2")
```

### 错误处理

- **参数数量验证**：确保传入的参数不超过已定义的参数数量
- **重复参数检测**：防止同一参数同时作为位置参数和关键字参数传入
- **缺失参数处理**：允许非必需参数缺失

## 执行上下文检测

包装器自动检测适当的执行模式：

```python
import asyncio

# Sync context
result = wrapper(a=1, b=2)  # Calls call_sync()

# Async context
async def async_context():
    result = await wrapper(a=1, b=2)  # Calls call_async()
```

## 子类化指南

创建子类时，请实现以下模式：

1. **初始化**：使用 name 和 parameters 调用 `super().__init__()`
2. **同步实现**：在 `call_sync()` 中处理同步执行
3. **异步实现**：在 `call_async()` 中处理异步执行
4. **参数验证**：使用 `_process_args()` 进行参数处理
5. **错误处理**：保留原始异常行为

## 集成

BaseToolWrapper 被所有集成模块使用：

- **OpenAPI**：OpenAPIToolWrapper
- **MCP**：MCPToolWrapper
- **LangChain**：LangChainToolWrapper
- **原生**：原生函数包装器

这确保了 ToolRegistry 生态系统中所有工具类型具有一致的执行语义。
