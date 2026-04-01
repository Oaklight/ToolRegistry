# Executor 后端

`executor` 包提供可插拔的执行后端，用于运行工具函数，支持并发、取消和超时。

## 概述

executor 包基于纯 `Callable + dict` 参数运行，**零导入** toolregistry 内部类型。`ToolRegistry.execute_tool_calls()` 自动将工具调用转换为此接口。

### 架构

```
ToolRegistry.execute_tool_calls()
    ↓
从 Tool 提取 callable + arguments
    ↓
backend.submit(fn, kwargs, timeout=...)
    ↓
ExecutionHandle（cancel、status、result、progress）
    ↓
收集结果 → dict[str, str]
```

## 后端

### ThreadBackend

线程池执行器，支持通过 `ExecutionContext` 实现**协作式取消**。

```python
from toolregistry.executor import ThreadBackend

backend = ThreadBackend(max_workers=4)
handle = backend.submit(my_func, {"x": 1, "y": 2}, timeout=10.0)
result = handle.result()
backend.shutdown()
```

特性：

- 通过 `ExecutionContext` 实现协作式取消
- 通过 `handle.on_progress(callback)` 报告进度
- 自动将异步函数包装为同步
- 自动注入 `_ctx: ExecutionContext` 参数

### ProcessPoolBackend

进程池执行器，使用 **cloudpickle 序列化**实现真正的并行。

```python
from toolregistry.executor import ProcessPoolBackend

backend = ProcessPoolBackend(max_workers=4)
handle = backend.submit(my_func, {"x": 1, "y": 2}, timeout=10.0)
result = handle.result()
backend.shutdown()
```

特性：

- 跨进程的真正并行执行
- 使用 cloudpickle 序列化传输函数
- 自动将异步函数包装为同步
- 通过 `future.cancel()` 硬取消（不支持协作式取消）

## ExecutionContext

工具函数可通过声明 `_ctx: ExecutionContext` 参数来支持协作式取消和进度报告：

```python
from toolregistry.executor import ExecutionContext

def long_running_task(data: list, _ctx: ExecutionContext) -> str:
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # 如果已取消则抛出 CancelledError
        process(item)
        _ctx.report_progress(fraction=(i + 1) / len(data), message=f"步骤 {i+1}")
    return "done"
```

后端在检测到 `_ctx` 参数时自动注入上下文，用户**不需要**显式传递。

**关键方法：**

| 方法 | 描述 |
|------|------|
| `cancelled` | 属性：如果已请求取消则为 `True` |
| `check_cancelled()` | 如果已取消则抛出 `CancelledError` |
| `report_progress(fraction, message, detail)` | 发出进度更新 |

## ExecutionHandle

由 `backend.submit()` 返回。用于控制和观察正在运行的执行。

| 方法 | 描述 |
|------|------|
| `result(timeout)` | 阻塞直到获取结果或超时 |
| `cancel()` | 请求取消 |
| `status()` | 返回 `ExecutionStatus`（PENDING、RUNNING、COMPLETED、FAILED、CANCELLED） |
| `on_progress(callback)` | 注册进度监听器 |
| `execution_id` | 此次执行的唯一标识 |

## ExecutionBackend Protocol

可通过实现 `ExecutionBackend` 协议来创建自定义后端：

```python
from toolregistry.executor import ExecutionBackend, ExecutionHandle

class MyBackend:
    def submit(self, fn, kwargs, *, execution_id=None, timeout=None) -> ExecutionHandle:
        ...

    def shutdown(self, wait=True) -> None:
        ...
```

## 与 ToolRegistry 集成

后端通过 `ToolRegistry` 透明使用：

```python
from toolregistry import ToolRegistry, ToolMetadata, Tool

registry = ToolRegistry()

# 设置默认执行模式
registry.set_default_execution_mode("thread")  # 或 "process"（默认）

# 单次调用覆盖
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")

# 通过 ToolMetadata 强制超时
tool = Tool.from_function(slow_func, metadata=ToolMetadata(timeout=5.0))
registry.register(tool)

# 并发安全控制
tool = Tool.from_function(unsafe_func, metadata=ToolMetadata(is_concurrency_safe=False))
registry.register(tool)
# 当批次中任何工具非并发安全时，整个批次顺序执行
```
