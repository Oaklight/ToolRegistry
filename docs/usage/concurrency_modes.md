# 执行模式：线程与进程

???+ note "更新日志"
    - 重构于版本：0.7.0（可插拔执行器后端）
    - 新增于版本：0.4.5

## 概览

ToolRegistry 使用可插拔的**执行器后端**并发执行工具调用。提供两种后端：

| 后端 | 类 | 适用场景 |
|------|---|---------|
| **线程** | `ThreadBackend` | 轻量级 CPU 密集型任务、共享内存场景 |
| **进程** | `ProcessPoolBackend` | 网络 I/O（MCP、OpenAPI）、崩溃隔离 |

进程模式是**默认模式** — 它为网络密集型工具提供更好的隔离和更高的吞吐量。

## 工作原理

当调用 `execute_tool_calls()` 时，ToolRegistry 将每个调用路由到选定的后端：

```
execute_tool_calls(tool_calls)
    ↓
从每个 Tool 中提取 callable + arguments
    ↓
backend.submit(fn, kwargs, timeout=...)  →  ExecutionHandle
    ↓
收集结果 → dict[str, str]
```

每次提交返回一个 `ExecutionHandle`，支持取消、状态查询和进度回调。详见 [Executor API 参考](../api/core/executor.md)。

## 线程模式

使用线程池（`concurrent.futures.ThreadPoolExecutor`），通过 `ExecutionContext` 实现协作式取消。

**优势：**

- CPU 密集型本地函数开销更低
- 共享内存 — 无需序列化
- 支持协作式取消和进度报告

**限制：**

- 受 GIL 限制，CPU 密集型任务无法真正并行
- 共享内存在高并发 I/O 下可能导致损坏或争用

## 进程模式（默认）

使用进程池，通过 **cloudpickle** 序列化实现真正的并行。

**优势：**

- 独立内存空间 — 工具调用之间的崩溃隔离
- 无 GIL — 真正的并行执行
- 网络 I/O（MCP、OpenAPI）吞吐量更高，因为事件循环互相隔离

**限制：**

- 进程间通信和序列化带来更高开销
- 不支持协作式取消（使用 `future.cancel()` 硬取消）
- 函数和参数必须可序列化

## 模式切换

### 永久更改

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.set_default_execution_mode("thread")  # 或 "process"（默认）
```

### 单次调用覆盖

```python
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
```

## 通过 ToolMetadata 控制并发

### 超时控制

通过 `ToolMetadata` 设置单工具超时，后端自动执行：

```python
from toolregistry import Tool, ToolMetadata

tool = Tool.from_function(slow_func, metadata=ToolMetadata(timeout=5.0))
registry.register(tool)
# 如果 slow_func 执行超过 5 秒，将被取消/超时
```

### 顺序执行

将工具标记为非并发安全，可强制整个批次顺序执行：

```python
tool = Tool.from_function(
    unsafe_func,
    metadata=ToolMetadata(is_concurrency_safe=False),
)
registry.register(tool)
# 当批次中任何工具的 is_concurrency_safe=False 时，
# 整个批次顺序执行
```

### 协作式取消（仅线程模式）

工具函数可通过接受 `_ctx` 参数实现协作式取消。后端自动注入：

```python
from toolregistry.executor import ExecutionContext

def long_task(data: list, _ctx: ExecutionContext) -> str:
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # 如果已取消则抛出 CancelledError
        process(item)
        _ctx.report_progress(fraction=(i + 1) / len(data), message=f"步骤 {i+1}")
    return "done"
```

!!! note
    `ExecutionContext` 仅在 `ThreadBackend` 中支持。进程模式下通过 `future.cancel()` 处理取消。

## 性能特征

以下基准测试比较了不同工具类型在线程和进程模式下的表现（每种 100 次并发调用）：

| 工具类型 | 线程模式 | 进程模式 |
|---------|---------|---------|
| 原生函数 | 4772 调用/秒 | 2357 调用/秒 |
| 原生类 | 12125 调用/秒 | 3011 调用/秒 |
| OpenAPI（网络） | 28 调用/秒 | 451 调用/秒 |
| MCP SSE（网络） | 27 调用/秒 | 132 调用/秒 |

**要点：**

- **本地函数**：线程模式更优，开销更低（无序列化、无 IPC）
- **网络 I/O（OpenAPI、MCP）**：进程模式大幅领先（5-16 倍），因为每个进程拥有独立的事件循环和网络连接，消除了争用
- **默认推荐**：使用进程模式，除非工作负载纯粹是本地 CPU 密集型函数

## 另请参阅

- [Executor 后端 API 参考](../api/core/executor.md) — `ThreadBackend`、`ProcessPoolBackend`、`ExecutionContext`、`ExecutionHandle`
- [工具元数据与标签](permissions.md#toolmetadata-fields) — `timeout`、`is_concurrency_safe`
