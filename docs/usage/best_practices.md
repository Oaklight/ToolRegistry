# 最佳实践

## 工具设计原则

### 编写清晰的文档字符串

ToolRegistry 从函数的文档字符串和类型提示生成参数 Schema 和描述。LLM 依赖这些描述来决定何时以及如何调用工具。

```python
@registry.register
def search_documents(query: str, limit: int = 10) -> list[dict]:
    """Search the document index for relevant results.

    Args:
        query: Natural language search query.
        limit: Maximum number of results to return (1-100).

    Returns:
        List of matching documents with title and snippet.
    """
    ...
```

!!! tip
    使用 Google 风格的文档字符串——ToolRegistry 的 Schema 生成器会自动解析 `Args:` 和 `Returns:` 段落。

### 使用简单类型

LLM 最适合处理基本类型（`str`、`int`、`float`、`bool`）和简单容器（`list`、`dict`）。避免将复杂自定义类型用作参数。

```python
# 推荐——LLM 可以轻松构造这些参数
def create_event(title: str, date: str, attendees: list[str]) -> str: ...

# 避免——LLM 无法构造 Pydantic 模型
def create_event(event: EventModel) -> str: ...
```

### 保持函数无状态

工具应仅依赖其输入参数，不依赖外部可变状态。这使工具在并发执行时安全，也更易于测试。

```python
# 推荐——纯函数
def celsius_to_fahrenheit(celsius: float) -> float:
    return celsius * 9 / 5 + 32

# 避免——依赖外部状态
last_result = None
def celsius_to_fahrenheit(celsius: float) -> float:
    global last_result
    last_result = celsius * 9 / 5 + 32
    return last_result
```

---

## ToolRegistry 特定实践

### 使用 ToolMetadata 和 ToolTag 分类工具

使用 `ToolMetadata` 和 `ToolTag` 声明行为特征。这些信息驱动权限系统和执行引擎。

```python
from toolregistry import ToolRegistry, Tool, ToolMetadata, ToolTag

registry = ToolRegistry()

# 标记只读工具
tool = Tool.from_function(
    get_weather,
    metadata=ToolMetadata(
        tags=[ToolTag.READ_ONLY, ToolTag.NETWORK],
        timeout=10.0,
    ),
)
registry.register(tool)

# 标记破坏性工具
tool = Tool.from_function(
    delete_file,
    metadata=ToolMetadata(
        tags=[ToolTag.DESTRUCTIVE, ToolTag.FILE_SYSTEM],
    ),
)
registry.register(tool)
```

可用标签：`READ_ONLY`、`DESTRUCTIVE`、`NETWORK`、`FILE_SYSTEM`、`SLOW`、`PRIVILEGED`。

### 为并发执行做设计

默认情况下，`execute_tool_calls()` 会并行运行多个工具调用。如果工具不适合并发执行（例如写入共享文件），需要显式标记：

```python
tool = Tool.from_function(
    write_to_log,
    metadata=ToolMetadata(is_concurrency_safe=False),
)
```

当批次中任何工具的 `is_concurrency_safe=False` 时，整个批次会顺序执行。

### 为长时间运行的工具使用协作式取消

执行长时间操作的工具应接受 `ExecutionContext` 参数以支持超时和取消：

```python
from toolregistry.executor import ExecutionContext

def process_large_dataset(data: list[str], _ctx: ExecutionContext) -> str:
    """Process a large dataset with progress reporting."""
    results = []
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # 超时时抛出 CancelledError
        results.append(transform(item))
        _ctx.report_progress(
            fraction=(i + 1) / len(data),
            message=f"Processed {i + 1}/{len(data)}",
        )
    return f"Processed {len(results)} items"
```

`_ctx` 参数由执行器自动注入——调用者无需显式传递。结合 `ToolMetadata(timeout=30.0)` 实现硬超时控制。

### 为外部调用设置超时

调用外部服务的工具应始终设置超时，防止执行器无限阻塞：

```python
tool = Tool.from_function(
    call_external_api,
    metadata=ToolMetadata(timeout=15.0, tags=[ToolTag.NETWORK]),
)
```

### 使用命名空间组织相关工具

从类或外部源注册多个工具时，使用命名空间避免名称冲突并提高可发现性：

```python
# 基于类的工具获得自动命名空间
registry.register_from_class(MathTools, namespace="math")
# 注册为：math-add、math-subtract、math-multiply

# 带命名空间的 MCP 工具
registry.register_from_mcp("http://localhost:8000/mcp", namespace="search")
```

### 清理资源

使用 MCP 或 OpenAPI 集成时，使用上下文管理器确保连接被正确关闭：

```python
# 推荐：上下文管理器
with ToolRegistry() as registry:
    registry.register_from_mcp("http://localhost:8000/mcp")
    results = registry.execute_tool_calls(tool_calls)

# 或显式清理
registry = ToolRegistry()
try:
    registry.register_from_mcp("http://localhost:8000/mcp")
    results = registry.execute_tool_calls(tool_calls)
finally:
    registry.close()
```

---

## 安全性

### 在系统边界进行验证

信任内部 ToolRegistry API，但验证来自外部源的输入（用户输入、LLM 输出、外部 API）：

```python
@registry.register
def execute_query(sql: str) -> list[dict]:
    """Execute a read-only SQL query."""
    # 执行前验证 LLM 生成的 SQL
    if any(keyword in sql.upper() for keyword in ["DROP", "DELETE", "UPDATE", "INSERT"]):
        return [{"error": "Only SELECT queries are allowed"}]
    return db.execute(sql)
```

### 使用权限系统

在生产部署中，配置 `PermissionPolicy` 来控制哪些工具可以被执行：

```python
from toolregistry.permissions import (
    PermissionPolicy,
    ALLOW_READONLY,
    ASK_DESTRUCTIVE,
    DENY_PRIVILEGED,
)

policy = PermissionPolicy(rules=[
    ALLOW_READONLY,      # 自动允许只读工具
    ASK_DESTRUCTIVE,     # 破坏性工具需要确认
    DENY_PRIVILEGED,     # 完全阻止特权工具
])
registry.set_permission_policy(policy)
```

参见[权限系统](permissions.md)获取完整指南。

---

## 测试

### 隔离测试工具

在注册之前独立测试工具函数：

```python
def test_calculate_area():
    assert calculate_area(3.0, 4.0) == 12.0
    assert calculate_area(0.0, 5.0) == 0.0
```

### 测试完整的 LLM 循环

对于集成测试，验证完整流程：Schema 生成 → 工具调用 → 执行 → 结果恢复：

```python
registry = ToolRegistry()
registry.register(calculate_area)

# 验证 Schema 生成
schemas = registry.get_schemas()
assert len(schemas) == 1
assert schemas[0]["function"]["name"] == "calculate_area"
```
