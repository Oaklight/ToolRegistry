# LangChainToolWrapper

提供异步和同步版本的 LangChain 工具调用的包装器类。

## 概览

`LangChainToolWrapper` 是专门为 LangChain 工具设计的包装器，提供 LangChain 丰富的工具生态系统与 ToolRegistry 标准化接口之间的无缝互操作。它保留 LangChain 原始的执行语义，同时支持与更广泛的 ToolRegistry 生态系统集成。

## 主要特性

- **LangChain 集成**：直接兼容 LangChain BaseTool 实例
- **执行保留**：保持 LangChain 原始的异步/同步执行行为
- **模式转换**：LangChain 和 ToolRegistry 模式之间的自动转换
- **错误透明性**：保留原始 LangChain 异常并增强上下文信息
- **参数映射**：不同模式格式之间的无缝参数处理
- **异步/同步桥接**：全面支持同步和异步执行

## 架构

LangChainToolWrapper 通过 LangChain 特定功能扩展了 `BaseToolWrapper`：

### 核心组件

1. **LangChain 工具管理**：直接与 LangChain BaseTool 实例集成
2. **模式转换**：将 LangChain 输入模式转换为 ToolRegistry 格式
3. **执行桥接**：保留 LangChain 的 _run() 和 _arun() 方法
4. **错误增强**：保持 LangChain 异常并添加额外上下文

### 集成流程

```
ToolRegistry 工具调用
    ↓
模式映射
    ↓
LangChain 工具执行 (_run/_arun)
    ↓
结果处理
    ↓
ToolRegistry 响应
```

## API 参考

::: toolregistry.langchain.integration.LangChainToolWrapper
    options:
      show_source: false
      show_root_heading: true
      show_root_toc_entry: false
      merge_init_into_class: true

## 使用示例

### 基本 LangChain 工具包装器

```python
from langchain_core.tools import BaseTool
from toolregistry.langchain.integration import LangChainToolWrapper

# Assume we have a LangChain tool
langchain_tool = BaseTool(
    name="calculator",
    description="Performs basic arithmetic operations",
    args_schema=CalculatorInput
)

# Create wrapper
wrapper = LangChainToolWrapper(tool=langchain_tool)

# Execute tool (automatic mode detection)
result = wrapper(a=5, b=3, operation="add")  # Sync - calls tool._run()
result = await wrapper(a=5, b=3, operation="add")  # Async - calls tool._arun()
```

### 自定义 LangChain 工具

```python
from langchain_core.tools import BaseTool, Tool
from pydantic import BaseModel, Field

class CalculatorInput(BaseModel):
    a: float = Field(description="First number")
    b: float = Field(description="Second number")
    operation: str = Field(description="Operation to perform")

def calculate(a: float, b: float, operation: str) -> float:
    """Perform calculation based on operation."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    # ... other operations

# Create LangChain tool
langchain_tool = Tool(
    name="calculator",
    description="Performs basic arithmetic operations",
    func=calculate,
    args_schema=CalculatorInput
)

# Wrap in ToolRegistry
wrapper = LangChainToolWrapper(langchain_tool)
```

## 模式转换

该包装器自动转换 LangChain 模式：

### LangChain 模式（Pydantic）
```python
class InputSchema(BaseModel):
    query: str = Field(description="Search query")
    limit: int = Field(description="Result limit", default=10)
```

### ToolRegistry 模式（JSON）
```python
{
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "limit": {"type": "integer", "description": "Result limit", "default": 10}
    },
    "required": ["query"]
}
```

### 自动转换
```python
# Wrapper handles the conversion automatically
langchain_tool = Tool(...)
wrapper = LangChainToolWrapper(langchain_tool)

# No manual schema conversion needed
result = wrapper(query="search term", limit=5)
```

## 执行模式

### 同步执行
```python
# Calls langchain_tool._run(*args, **kwargs)
wrapper = LangChainToolWrapper(langchain_tool)
result = wrapper(param1="value1", param2="value2")
```

### 异步执行
```python
# Calls langchain_tool._arun(*args, **kwargs)
wrapper = LangChainToolWrapper(langchain_tool)
result = await wrapper(param1="value1", param2="value2")
```

### 自动模式检测
```python
import asyncio

# Detects execution context automatically
result1 = wrapper(arg="value")  # Sync context → _run()
result2 = await wrapper(arg="value")  # Async context → _arun()
```

## 集成模式

### 与 LangChain 集成配合使用

```python
from toolregistry import ToolRegistry
from toolregistry.langchain import LangChainIntegration

registry = ToolRegistry()
langchain_integration = LangChainIntegration(registry)

# Register single LangChain tool
await langchain_integration.register_langchain_tools_async(langchain_tool)

# Tool is automatically wrapped with LangChainToolWrapper
```

### 直接使用包装器

```python
# For immediate tool wrapping
wrapper = LangChainToolWrapper(langchain_tool)

# Use directly or register in ToolRegistry
registry.register(wrapper)
```

## 错误处理

该包装器保留 LangChain 原始的错误处理：

### LangChain 异常
```python
# Original LangChain exceptions are preserved
from langchain_core.tools import ToolException

try:
    result = wrapper(invalid_param="value")
except ToolException as e:
    # Original LangChain exception with enhanced context
    print(f"LangChain Error: {e}")
```

### 增强的错误上下文
```python
try:
    result = wrapper(param="value")
except Exception as e:
    # Enhanced with wrapper context while preserving original
    logger.error(f"Error in {wrapper.name}: {traceback.format_exc()}")
    raise  # Original exception is re-raised
```

## 支持的 LangChain 工具类型

### 函数工具
```python
from langchain_core.tools import Tool

def my_function(input: str) -> str:
    return f"Processed: {input}"

tool = Tool(name="my_tool", func=my_function)
wrapper = LangChainToolWrapper(tool)
```

### 结构化工具
```python
from langchain_core.tools import StructuredTool

def structured_function(query: str, limit: int) -> List[str]:
    return ["result1", "result2"]

tool = StructuredTool.from_function(structured_function)
wrapper = LangChainToolWrapper(tool)
```

### BaseTool 子类
```python
from langchain_core.tools import BaseTool

class CustomTool(BaseTool):
    name = "custom_tool"
    description = "Custom tool description"

    def _run(self, query: str) -> str:
        return f"Custom result: {query}"

    async def _arun(self, query: str) -> str:
        return f"Custom async result: {query}"

wrapper = LangChainToolWrapper(CustomTool())
```

## 集成优势

### 非侵入式集成
- 保留原始 LangChain 工具行为
- 无需修改现有 LangChain 工具
- 与 LangChain 应用向后兼容

### ToolRegistry 优势
- 所有工具类型的统一接口
- 命名空间组织支持
- 跨框架工具发现
- 增强的错误日志和调试

LangChainToolWrapper 实现了 LangChain 丰富工具生态系统与 ToolRegistry 框架的无缝集成，融合了两者的优势：LangChain 经过验证的工具实现与 ToolRegistry 标准化的执行接口。
