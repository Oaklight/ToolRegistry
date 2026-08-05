# 执行后端与异步支持

???+ note "更新日志"
    - **未发布**：InlineBackend、`ainvoke` / `aexecute_tool_calls`、按工具解析后端、同步 inline→thread 提升、`natural_backend`、移除 `force_thread`
    - 重构于版本：0.7.0（可插拔执行器后端）
    - 新增于版本：0.4.5

## 概览

ToolRegistry 提供**三种执行后端**和**同步/异步**两套入口。调用接口（同步/异步）与执行后端（inline/thread/process）正交——你根据自己的上下文选择接口，每个工具自动解析到其自然后端。

### 后端

| 后端 | 类 | 隔离 | 超时 | 适用场景 |
|------|-----|------|------|---------|
| **Inline** | `InlineBackend` | 无 | ✅ 异步路径（`wait_for`） | MCP、OpenAPI、已在外部隔离的工具 |
| **Thread** | `ThreadBackend` | 线程 | ✅ `Future.result(t)` | 同步调用方、超时强制执行、共享内存任务 |
| **Process** | `ProcessPoolBackend` | 进程 | ✅ `Future.result(t)` | CPU 隔离、故障隔离（cloudpickle） |

### 入口

| 入口 | 返回类型 | 后端默认 |
|------|---------|---------|
| `invoke(name, kwargs)` | `ToolCallResult \| ErrorResult` | Inline 工具 → thread；其他 → inline |
| `ainvoke(name, kwargs)` | `ToolCallResult \| ErrorResult` | Inline 工具 → inline（原生 `await`） |
| `execute_tool_calls(tcs)` | `ResultList` | 按工具：`natural_backend` → registry 默认（`process`） |
| `aexecute_tool_calls(tcs)` | `ResultList` | 按工具：inline 工具在调用方 loop 上重叠 |

四个入口均返回结构化的 `Result` 类型，对访问控制失败（缺失、禁用、拒绝）**不抛异常**，而是返回 `ErrorResult`。

## 按工具解析后端

`_resolve_backend` 接缝**按工具**解析后端，而非按批次：

```
1. 调用方显式 execution_mode ("thread" / "process")  → 最优先
2. tool.metadata.natural_backend ("inline" / "thread" / "process")  → 工具偏好
3. 上下文默认  → 单次调用为 inline，批量为 registry._execution_mode
```

额外规则：**同步入口上，inline 被提升为 thread**，使 `Future.result(timeout)` 提供真正的截止时间。异步入口保持 inline，因为它们需要协程在自己的 event loop 上运行。

### `natural_backend`

MCP 和 OpenAPI 工具在注册时自动设置 `natural_backend="inline"`——它们的活连接（MCP `ClientSession`、httpx socket）绑定在 event loop 上，无法 pickle 进进程池。PTC 的 `programmatic_tool_call` 工具也使用 `natural_backend="inline"`，因为其 IPC 回调必须留在调用进程。

```python
from toolregistry import Tool, ToolMetadata

# 显式设置工具的首选后端
tool = Tool.from_function(my_func, metadata=ToolMetadata(natural_backend="thread"))
registry.register(tool)
```

## 异步支持

### `ainvoke`

`invoke()` 的异步版本。对于 inline 解析的工具（MCP、OpenAPI、async 原生函数），协程直接在调用方的 event loop 上 await——无线程跳转、无 `asyncio.run()`：

```python
result = await registry.ainvoke("mcp_tool", {"query": "hello"})
assert isinstance(result, ToolCallResult)
```

### `aexecute_tool_calls`

通过 `asyncio.gather` 实现的异步批量执行。Inline 工具在调用方 loop 上重叠执行；池后端工具提交后 `await handle.result_async()`：

```python
results = await registry.aexecute_tool_calls(tool_calls)
```

并发安全的工具并行运行；如有工具设置了 `is_concurrency_safe=False`，整批串行执行（与同步路径行为一致）。

## Inline 后端

在当前上下文运行目标，无池。使用**惰性捕获**——`submit()` 存储 callable；执行推迟到 `result()`（同步）或 `result_async()`（异步）。

- **异步路径**：`result_async()` 原生 await 协程。超时通过 `asyncio.wait_for` 强制执行。
- **同步路径**：同步入口上，inline 解析的工具被**提升到线程后端**，获得 `Future.result(timeout)` 的真正超时。此提升由 `_resolve_backend` 透明处理。

Inline 后端适用于已在外部隔离的工具（MCP 服务器运行在独立进程中；OpenAPI 工具是纯 HTTP）——对其 transport 进行池化或 pickle 是错误或不可能的。

## Thread 后端

使用 `concurrent.futures.ThreadPoolExecutor`，通过 `ExecutionContext` 支持协作式取消。

**优势：**

- CPU 密集型本地函数开销更低
- 共享内存——无需序列化
- 协作式取消和进度报告
- 通过 `Future.result(timeout)` 实现真正的超时

**限制：**

- CPU 密集型并行受 GIL 限制

### 协作式取消

工具函数可通过接受 `_ctx` 参数加入协作式取消：

```python
from toolregistry.executor import ExecutionContext

def long_task(data: list, _ctx: ExecutionContext) -> str:
    for i, item in enumerate(data):
        _ctx.check_cancelled()  # 被取消时抛出 CancelledError
        process(item)
        _ctx.report_progress(fraction=(i + 1) / len(data))
    return "done"
```

## Process 后端（批量默认）

使用进程池和 **cloudpickle** 序列化实现真正的并行。

**优势：**

- 独立内存空间——崩溃隔离
- 无 GIL——真正的并行执行

**限制：**

- 进程间通信开销更高
- 不支持协作式取消
- 函数和参数必须可 pickle
- MCP/OpenAPI 工具**不能**使用此后端（活连接不可 pickle）

## 切换模式

### 永久更改

```python
registry.set_default_execution_mode("thread")  # 或 "process"（默认）
```

### 按次覆盖

```python
results = registry.execute_tool_calls(tool_calls, execution_mode="thread")
result = registry.invoke("tool", args, execution_mode="process")
```

## 超时

通过 `ToolMetadata.timeout` 设置工具级超时：

```python
tool = Tool.from_function(slow_func, metadata=ToolMetadata(timeout=5.0))
```

超时强制执行取决于路径：

| 入口 | 后端 | 强制执行？ | 机制 |
|------|------|----------|------|
| `invoke()` | thread（提升） | ✅ | `Future.result(timeout)` |
| `ainvoke()` | inline | ✅ | `asyncio.wait_for` |
| `execute_tool_calls()` | thread/process | ✅ | `Future.result(timeout)` |
| `aexecute_tool_calls()` | inline | ✅ | `asyncio.wait_for` |

## 串行执行

将工具标记为非并发安全以强制整批串行执行：

```python
tool = Tool.from_function(
    unsafe_func,
    metadata=ToolMetadata(is_concurrency_safe=False),
)
```

## 另请参阅

- [架构概览](../architecture/overview.md) — 执行栈图
- [执行器后端 API 参考](../api/core/executor.md) — `InlineBackend`、`ThreadBackend`、`ProcessPoolBackend`、`ExecutionHandle`
