# 并发模式：线程模式和进程模式

???+ note "更新日志"
    新增于版本：0.4.5

## 概览

在版本 0.4.5 之前，执行模式由 `tool_calls` 中的任务数量决定。对于两个或更少的任务，主线程按顺序执行它们。对于超过两个任务，使用线程池进行并行执行。

版本 0.4.5 引入了并发进程模式作为默认执行模式，确保增强的隔离和崩溃预防。并发线程模式仍然可用作需要共享内存或较低开销场景的可选备份。

## 设计概念

### 线程模式

- **目的**：适用于需要共享内存和最小开销的轻量级任务。
- **优势**：
  - 更快的上下文切换。
  - 共享内存访问。
- **限制**：
  - 由于共享内存损坏而容易崩溃。

### 进程模式

- **目的**：适用于需要高隔离和安全性的任务。
- **优势**：
  - 独立的内存空间。
  - 增强的崩溃抵抗力。
- **限制**：
  - 由于进程间通信而产生更高的开销。

## 模式切换

### 配置

可以通过修改 ToolRegistry 配置或在执行期间覆盖来切换模式。以下步骤概述了该过程：

默认情况下，`ToolRegistry` 初始化时将 `parallel_mode` 设置为 `"process"`。要永久更改模式，请使用 `set_execution_mode` 方法。对于单次使用覆盖，在 `execute_tool_calls` 方法中提供 `parallel_mode` 参数。

#### 示例

1. **线程模式**：

   - 将执行模式设置为 `thread`。
   - 示例：

     ```python
     tool_registry.set_execution_mode("thread")
     ```

2. **进程模式（默认）**：

   - 将执行模式设置为 `process`。
   - 示例：

     ```python
     tool_registry.set_execution_mode("process")
     ```

3. **单次使用覆盖**：

   - 在执行期间覆盖模式。
   - 示例：

     ```python
     tool_registry.execute_tool_calls(tool_calls, parallel_mode="thread")
     ```

## 性能和结果

为了评估并发执行模式的性能，我们使用脚本 [`examples/test_toolregistry_concurrency.py`](https://github.com/Oaklight/ToolRegistry/blob/concurrent%2Bdill/examples/test_toolregistry_concurrency.py) 进行了实验。测试涉及在四种场景中执行 100 个工具调用（`N = 100`）：原生函数工具、原生类工具、OpenAPI 工具和 MCP SSE 工具。每个工具调用执行简单的随机数学运算（`add`、`subtract`、`multiply` 和 `divide`）。测试在 `"process"` 和 `thread` 模式下测量执行时间和吞吐量。

### 并发模式性能比较

#### 性能日志

```bash
$ EXEC_MODE=thread python examples/test_toolregistry_concurrency.py
---------- Native Func Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.021 seconds
Average throughput: 4772.17 calls/second
---------- Native Class Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.0083 seconds
Average throughput: 12125.03 calls/second
---------- OpenAPI Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 3.5234 seconds
Average throughput: 28.40 calls/second
---------- MCP SSE Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 3.6547 seconds
Average throughput: 27.39 calls/second

$ EXEC_MODE=process python examples/test_toolregistry_concurrency.py
---------- Native Func Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.0425 seconds
Average throughput: 2357.26 calls/second
---------- Native Class Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.0332 seconds
Average throughput: 3010.66 calls/second
---------- OpenAPI Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.2216 seconds
Average throughput: 451.28 calls/second
---------- MCP SSE Tool ----------
Success rate: 100.00% (100/100)
Average execution time: 0.7551 seconds
Average throughput: 132.44 calls/second
```

注意：此计算由 `cicada-agent` 使用包含 `Calculator` 和 `FileOps` 的 `ToolRegistry` 作为演示完成。

#### 分析

1. **MCP 集成实现**

- MCP 工具同步调用在每次调用时创建和关闭事件循环，造成开销。
- 异步调用使用 SSE 长连接和事件循环，具有网络 I/O 和事件循环调度开销。
- 线程模式在线程间共享进程资源，在事件循环和网络连接中造成资源争用，导致性能瓶颈（27.39 调用/秒）。
- 进程模式每个进程使用独立的事件循环和网络连接，减少争用并提高吞吐量（132.44 调用/秒）。

2. **OpenAPI 集成实现**

- OpenAPI 工具同步调用使用 httpx 同步客户端；异步调用使用 httpx 异步客户端。
- 线程模式下许多线程发出网络请求会导致线程切换和网络 I/O 争用，降低性能（28.40 调用/秒）。
- 进程模式使用独立进程，避免 GIL 和线程上下文切换开销，改善网络 I/O 调度（451.28 调用/秒）。

3. **原生本地工具调用**

- 原生函数和类工具调用主要是 CPU 和内存操作；线程模式释放 GIL 并具有低线程切换开销，导致更好的性能（函数 4772.17 调用/秒，类 12125.03 调用/秒）。
<!-- - 类工具显示更高的吞吐量，因为更高效的方法绑定和减少的每次调用开销 -->
- 进程模式实现真正的并行性但具有更高的开销，与线程模式相比吞吐量较低（函数 2357.26 调用/秒，类 3010.66 调用/秒）。

#### 总结

- OpenAPI 和 MCP 调用涉及网络 I/O 和事件循环管理；线程模式受到资源争用和事件循环开销的影响，降低性能。
- 进程模式隔离资源，避免争用，并提高网络调用吞吐量。
- 进程模式在 tool_call 用例中实现了相当的性能并提供更好的安全防护。因此我们通常建议将执行模式保留为默认的 `process`。
