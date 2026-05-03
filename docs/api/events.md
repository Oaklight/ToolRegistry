# 事件

事件模块为 ToolRegistry 回调机制提供事件基础设施，使订阅者能够在工具状态发生变化时接收通知。

## 概述

回调机制允许外部组件对 ToolRegistry 中的变化做出响应，例如工具注册、启用或禁用。这对以下场景特别有用：

- **UI 更新**：刷新管理面板中的工具列表
- **日志记录**：跟踪工具生命周期事件
- **同步**：保持外部系统与注册表状态同步
- **监控**：观察工具使用模式

## ChangeEventType

枚举 ToolRegistry 中可能发生的所有变更事件类型。

### 值

| 值 | 描述 |
|-------|-------------|
| `REGISTER` | 工具已注册 |
| `UNREGISTER` | 工具已注销（预留，暂未使用） |
| `ENABLE` | 工具已启用 |
| `DISABLE` | 工具已禁用 |
| `REFRESH` | 单个工具已刷新（预留，暂未使用） |
| `REFRESH_ALL` | 所有工具已刷新/重新加载（预留，暂未使用） |
| `PERMISSION_DENIED` | 工具调用被权限策略拒绝 |
| `PERMISSION_ASKED` | 工具调用被上报给权限处理器 |
| `METADATA_UPDATE` | 工具的元数据在运行时被更新 |

### 示例

```python
from toolregistry import ChangeEventType

# 检查事件类型
if event.event_type == ChangeEventType.REGISTER:
    print("新工具已注册！")
elif event.event_type == ChangeEventType.DISABLE:
    print(f"工具已禁用：{event.reason}")
elif event.event_type == ChangeEventType.PERMISSION_DENIED:
    print(f"工具调用被拒绝：{event.tool_name}")
elif event.event_type == ChangeEventType.PERMISSION_ASKED:
    print(f"工具调用被上报：{event.tool_name}")
elif event.event_type == ChangeEventType.METADATA_UPDATE:
    print(f"元数据已更新：{event.tool_name}，字段：{event.metadata}")
```

## ChangeEvent

表示注册表中变更事件的不可变数据类。

### 属性

| 属性 | 类型 | 描述 |
|-----------|------|-------------|
| `event_type` | `ChangeEventType` | 发生的变更类型 |
| `tool_name` | `str \| None` | 受影响工具的名称，批量操作时为 `None` |
| `reason` | `str \| None` | 可选的原因字符串，主要用于禁用事件 |
| `metadata` | `dict[str, Any]` | 可选的附加上下文数据（默认为空字典） |

### 示例

```python
from toolregistry import ChangeEvent, ChangeEventType

# 事件由 ToolRegistry 内部创建
# 以下是它们的结构：
event = ChangeEvent(
    event_type=ChangeEventType.REGISTER,
    tool_name="calculator.add",
)

# 访问事件属性
print(f"事件：{event.event_type.value}")  # "register"
print(f"工具：{event.tool_name}")          # "calculator.add"

# 带原因的禁用事件
disable_event = ChangeEvent(
    event_type=ChangeEventType.DISABLE,
    tool_name="risky_tool",
    reason="检测到安全漏洞",
)
```

## ChangeCallback

处理变更事件的回调函数的类型别名。

### 签名

```python
ChangeCallback = Callable[[ChangeEvent], None]
```

回调接收一个 `ChangeEvent` 并且不返回任何值。回调应该是轻量级的，不应抛出需要传播的异常。

## API 参考

::: toolregistry.events
    options:
        show_source: false
        show_root_heading: false
        show_root_toc_entry: false
        members:
            - ChangeEventType
            - ChangeEvent
            - ChangeCallback

## 与 ToolRegistry 配合使用

### 注册回调

使用 `on_change()` 注册一个回调，该回调将收到所有变更事件的通知：

```python
from toolregistry import ToolRegistry, ChangeEvent, ChangeEventType

registry = ToolRegistry()

def my_callback(event: ChangeEvent) -> None:
    """处理工具注册表变更。"""
    print(f"[{event.event_type.value}] {event.tool_name}")
    if event.reason:
        print(f"  原因：{event.reason}")

# 注册回调
registry.on_change(my_callback)

# 现在任何变更都会触发回调
def add(a: int, b: int) -> int:
    return a + b

registry.register(add)  # 输出：[register] add
registry.disable("add", reason="维护中")  # 输出：[disable] add，原因：维护中
registry.enable("add")  # 输出：[enable] add
```

### 移除回调

使用 `remove_on_change()` 取消注册回调：

```python
# 不再需要时移除回调
removed = registry.remove_on_change(my_callback)
print(f"回调已移除：{removed}")  # True

# 后续变更不会触发回调
registry.register(another_function)  # 无输出
```

### 多个回调

可以注册多个回调，它们将按注册顺序被调用：

```python
def logger_callback(event: ChangeEvent) -> None:
    logging.info(f"工具事件：{event.event_type.value} - {event.tool_name}")

def metrics_callback(event: ChangeEvent) -> None:
    metrics.increment(f"tool.{event.event_type.value}")

registry.on_change(logger_callback)
registry.on_change(metrics_callback)

# 每次变更都会调用两个回调
registry.register(some_tool)
```

### 错误处理

回调不应抛出异常。如果回调抛出异常，异常会被记录但不会阻止其他回调被调用：

```python
def faulty_callback(event: ChangeEvent) -> None:
    raise ValueError("出错了！")

def reliable_callback(event: ChangeEvent) -> None:
    print(f"收到事件：{event.event_type.value}")

registry.on_change(faulty_callback)
registry.on_change(reliable_callback)

# faulty_callback 的异常被记录，但 reliable_callback 仍然运行
registry.register(some_tool)  # 输出：收到事件：register
```

## 线程安全

回调机制是线程安全的：

- 回调使用锁以线程安全的方式存储
- 回调调用时会复制回调列表，以允许在迭代期间安全修改
- 每个回调在调用线程中同步调用

## 最佳实践

1. **保持回调轻量**：繁重的处理应该卸载到单独的线程或任务队列
2. **不要抛出异常**：在回调内处理错误或记录它们
3. **避免阻塞操作**：对 I/O 密集型工作使用异步模式
4. **清理回调**：不再需要时移除回调以防止内存泄漏

```python
# 好的做法：轻量级回调，将工作排队
def async_handler(event: ChangeEvent) -> None:
    task_queue.put(event)  # 快速、非阻塞

# 不好的做法：在回调中进行繁重处理
def slow_handler(event: ChangeEvent) -> None:
    time.sleep(5)  # 阻塞注册表操作
    database.save(event)  # 在回调中进行 I/O
```
