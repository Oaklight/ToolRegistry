# Tool

表示 ToolRegistry 生态系统中具有元数据和执行逻辑的单个工具。

## 概览

`Tool` 类是 ToolRegistry 系统中所有工具的基础抽象。它封装了可执行逻辑以及工具发现、参数验证和在 LLM 应用中执行所需的元数据。

## 主要特性

- **元数据管理**：全面的工具描述、参数和执行元数据
- **参数验证**：内置参数模式验证和类型检查
- **执行抽象**：同步和异步执行的统一接口
- **命名空间支持**：与命名空间组织集成，用于工具分组
- **可调用集成**：通过可调用接口直接执行

## 架构

Tool 类遵循数据传输对象模式，包含以下关键组件：

### 核心属性

1. **name**：工具的唯一标识符
2. **description**：人类可读的工具功能描述
3. **parameters**：定义预期参数的 JSON Schema
4. **callable**：实际的可执行函数或包装器
5. **is_async**：指示异步执行能力的标志
6. **namespace**：可选的组织命名空间（存储规范化后的原始命名空间字符串）
7. **method_name**：可选的命名空间前缀添加前的原始方法/函数名称（保留用于无歧义的基础名称恢复）

### 计算属性

- **qualified_name**：返回完全限定的工具名称。如果同时设置了 `namespace` 和 `method_name`，则返回 `{namespace}-{method_name}`；否则回退到 `name` 字段。

### 设计理念

- **不可变性**：Tool 实例设计为创建后不可变
- **模式驱动**：基于 JSON Schema 标准的参数验证
- **执行灵活性**：支持同步和异步执行模式
- **元数据保留**：完整保留工具元数据以供 LLM 使用

## API 参考

::: toolregistry.Tool
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true

## 使用示例

### 基本工具创建

```python
from toolregistry import Tool

def calculate_area(length: float, width: float) -> float:
    """Calculate the area of a rectangle."""
    return length * width

# Create a Tool instance
area_tool = Tool(
    name="calculate_area",
    description="Calculate the area of a rectangle",
    parameters={
        "type": "object",
        "properties": {
            "length": {"type": "number", "description": "Length of rectangle"},
            "width": {"type": "number", "description": "Width of rectangle"}
        },
        "required": ["length", "width"]
    },
    callable=calculate_area,
    is_async=False
)
```

### 带命名空间的工具

```python
from toolregistry import Tool

# Create a tool with namespace and method_name fields
math_tool = Tool(
    name="math_ops-multiply",
    description="Multiply two numbers",
    parameters={
        "type": "object",
        "properties": {
            "a": {"type": "number"},
            "b": {"type": "number"}
        },
        "required": ["a", "b"]
    },
    callable=lambda a, b: a * b,
    is_async=False,
    namespace="math_ops",
    method_name="multiply",
)

# Access the qualified name
print(math_tool.qualified_name)  # Output: "math_ops-multiply"
print(math_tool.namespace)       # Output: "math_ops"
print(math_tool.method_name)     # Output: "multiply"
```

### 通过函数创建带命名空间的工具

```python
from toolregistry import Tool

def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

# Create a tool with namespace using from_function()
tool = Tool.from_function(multiply, namespace="math_ops")
print(tool.name)            # Output: "math_ops-multiply"
print(tool.namespace)       # Output: "math_ops"
print(tool.method_name)     # Output: "multiply"
print(tool.qualified_name)  # Output: "math_ops-multiply"

# You can also provide a custom method_name
tool2 = Tool.from_function(multiply, namespace="math_ops", method_name="mul")
print(tool2.name)            # Output: "math_ops-mul"
print(tool2.method_name)     # Output: "mul"
```

### 更新命名空间

```python
from toolregistry import Tool

# Create a tool without namespace
math_tool = Tool.from_function(lambda a, b: a * b, name="multiply")

# Update with namespace
math_tool.update_namespace("math_operations")
print(math_tool.name)           # Output: "math_operations-multiply"
print(math_tool.namespace)      # Output: "math_operations"
print(math_tool.method_name)    # Output: "multiply"
print(math_tool.qualified_name) # Output: "math_operations-multiply"
```

### 异步工具

```python
import asyncio
from toolregistry import Tool

async def fetch_data(url: str) -> dict:
    """Fetch data from a URL asynchronously."""
    # Async implementation
    return {"url": url, "data": "sample"}

# Create async tool
async_tool = Tool(
    name="fetch_data",
    description="Fetch data from URL",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch from"}
        },
        "required": ["url"]
    },
    callable=fetch_data,
    is_async=True
)
```

## 参数模式格式

Tool 类使用 JSON Schema 格式进行参数验证：

```json
{
  "type": "object",
  "properties": {
    "param_name": {
      "type": "string|number|boolean|array|object",
      "description": "Parameter description",
      "default": "default_value"
    }
  },
  "required": ["param1", "param2"]
}
```

## 与 ToolRegistry 集成

工具主要通过 ToolRegistry 使用：

```python
from toolregistry import ToolRegistry, Tool

registry = ToolRegistry()

# Register tool with registry
registry.register(tool_instance)

# Execute tool through registry
result = registry.execute_tool("tool_name", param1="value1", param2="value2")
```

Tool 类为 ToolRegistry 生态系统中的所有工具操作提供了基础，确保在不同工具来源和执行环境中具有一致的行为。
