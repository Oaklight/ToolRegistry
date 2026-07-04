# ToolRegistry

管理工具注册、执行和元数据的中央注册表类。

## 概述

`ToolRegistry` 是 ToolRegistry 库中工具管理的核心协调器。它提供了一个统一的接口，用于注册、发现和执行来自各种来源的工具，包括原生 Python 函数、OpenAPI 规范、MCP 服务器、LangChain 工具等。

## 核心特性

- **统一工具管理**：所有类型工具的中央注册表
- **异步/同步支持**：完全兼容同步和异步执行
- **命名空间组织**：支持在命名空间下组织工具
- **多源集成**：与各种工具源无缝集成
- **元数据保留**：维护工具描述、参数和执行元数据
- **灵活执行**：多种执行模式和并发选项
- **变更回调**：通过 `on_change()` / `remove_on_change()` 订阅工具状态变更
- **注册后钩子**：通过 `add_post_register_hook()` 在每个工具注册完成后运行自定义逻辑，支持自动禁用
- **基于标签的批量禁用**：通过 `disable_by_tags()` 按 `ToolTag` 值批量禁用多个工具

## 架构

ToolRegistry 遵循注册表模式，具有以下核心职责：

### 核心职责

1. **工具注册**：接受并注册来自各种来源的工具
2. **工具发现**：提供发现可用工具的机制
3. **工具执行**：使用适当的参数验证和错误处理执行工具
4. **元数据管理**：维护并提供对工具元数据的访问
5. **命名空间支持**：在逻辑命名空间下组织工具

### 注册方法

- **原生注册**：`register()` 用于直接函数/实例注册
- **类集成**：`register_from_class()` 用于 Python 类方法注册。默认情况下，遍历 MRO（方法解析顺序）以包含从父类继承的方法。传递 `traverse_mro=False` 仅注册直接定义的方法。
- **OpenAPI 集成**：与 OpenAPI 规范集成
- **MCP 集成**：支持模型上下文协议服务器
- **LangChain 集成**：与 LangChain 工具兼容

### 执行模型

- **`invoke(tool_name, kwargs)`**：单工具执行，走完整 pipeline（权限、日志、调用追踪）。PTC 的 IPC 回调使用此方法。
- **`execute_tool_calls(tool_calls)`**：批量执行，通过 Thread/Process 后端并发。用于 LLM tool_use 响应。
- **`registry.ptc.enable()`**：注册 `programmatic_tool_call` 工具用于[程序化工具调用](../../usage/programmatic_tool_calling.md)。LLM 可以编写 Python 代码编排多个工具调用。

### 调用追踪

所有工具执行都带有 `invocation_id` 前缀记录日志：

- `tr_sig_` — 单次 `invoke()` 调用
- `tr_bat_` — 批量 `execute_tool_calls()` 调用
- `tr_ptc_` — PTC 代码执行工具调用

查询：`log.get_entries(invocation_id="tr_ptc_...")`

## API 参考

::: toolregistry.ToolRegistry
    options:
        show_source: false
        show_root_heading: true
        show_root_toc_entry: false
        merge_init_into_class: true
        separate_signature: true
        show_signature_annotations: true

## 使用示例

### 基本工具注册

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# 注册一个简单函数
def add_numbers(a: int, b: int) -> int:
    return a + b

registry.register(add_numbers)
```

### 类集成

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

class Calculator:
    @staticmethod
    def multiply(a: int, b: int) -> int:
        return a * b

    def divide(self, a: int, b: int) -> float:
        return a / b

# 注册类中的所有方法
registry.register_from_class(Calculator)
```

### 带 MRO 遍历的类集成

```python
from toolregistry import ToolRegistry

class BaseCalculator:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b

class AdvancedCalculator(BaseCalculator):
    @staticmethod
    def multiply(a: int, b: int) -> int:
        return a * b

registry = ToolRegistry()

# 默认行为（traverse_mro=True）：包含从 BaseCalculator 继承的方法
registry.register_from_class(AdvancedCalculator)
print(registry.get_available_tools())
# 输出：['advanced_calculator-add', 'advanced_calculator-multiply']

# 使用 traverse_mro=False：仅注册直接定义在 AdvancedCalculator 上的方法
registry2 = ToolRegistry()
registry2.register_from_class(AdvancedCalculator, traverse_mro=False)
print(registry2.get_available_tools())
# 输出：['advanced_calculator-multiply']
```

### 命名空间组织

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# 使用自定义命名空间注册
registry.register(my_function, namespace="math_utils")

# 使用命名空间访问工具
available_tools = registry.get_available_tools(namespace="math_utils")
```

### 变更回调

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

# 变更将触发回调
def add(a: int, b: int) -> int:
    return a + b

registry.register(add)  # 触发：[register] add
registry.disable("add", reason="维护中")  # 触发：[disable] add
registry.enable("add")  # 触发：[enable] add

# 不再需要时移除回调
registry.remove_on_change(my_callback)
```

### 可观测性 API

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

def add(a: int, b: int) -> int:
    return a + b

def subtract(a: int, b: int) -> int:
    return a - b

registry.register(add)
registry.register(subtract)

# 禁用一个工具并提供原因
registry.disable("subtract", reason="维护中")

# 获取所有工具的状态
status = registry.get_tools_status()
print(status)
# 输出：
# [
#     {"name": "add", "enabled": True, "reason": None, "namespace": None},
#     {"name": "subtract", "enabled": False, "reason": "维护中", "namespace": None}
# ]

# 筛选出已禁用的工具
disabled_tools = [s for s in status if not s["enabled"]]
print(disabled_tools)
# 输出：[{"name": "subtract", "enabled": False, "reason": "维护中", "namespace": None}]
```

### 基于标签的批量禁用

```python
from toolregistry import ToolRegistry, ToolMetadata, ToolTag

registry = ToolRegistry()

def read_file(path: str) -> str:
    """从磁盘读取文件。"""
    ...

def delete_file(path: str) -> None:
    """从磁盘删除文件。"""
    ...

def send_email(to: str, body: str) -> None:
    """发送电子邮件。"""
    ...

registry.register(read_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.READ_ONLY}))
registry.register(delete_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.DESTRUCTIVE}))
registry.register(send_email, metadata=ToolMetadata(tags={ToolTag.NETWORK}))

# match="any"（默认）：工具拥有至少一个指定标签即被禁用
disabled = registry.disable_by_tags(
    {ToolTag.DESTRUCTIVE, ToolTag.NETWORK},
    match="any",
    reason="只读模式下限制访问",
)
print(disabled)  # ['delete_file', 'send_email']

# match="all"：工具携带全部指定标签才被禁用
registry2 = ToolRegistry()
registry2.register(read_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.READ_ONLY}))
registry2.register(delete_file, metadata=ToolMetadata(tags={ToolTag.FILE_SYSTEM, ToolTag.DESTRUCTIVE}))

disabled2 = registry2.disable_by_tags(
    {ToolTag.FILE_SYSTEM, ToolTag.DESTRUCTIVE},
    match="all",
    reason="不允许破坏性文件系统操作",
)
print(disabled2)  # ['delete_file']
```

### 注册后钩子

```python
from toolregistry import ToolRegistry, PostRegisterHook, ToolMetadata, ToolTag

registry = ToolRegistry()

# 钩子：在注册时自动禁用所有特权工具
def deny_privileged(tool_name: str, tool, registry) -> str | None:
    tags = tool.metadata.tags if tool.metadata else set()
    if ToolTag.PRIVILEGED in tags:
        return f"当前环境不允许特权工具 '{tool_name}'"
    return None

registry.add_post_register_hook(deny_privileged)

def sudo_command(cmd: str) -> str:
    """以提升的权限运行命令。"""
    ...

registry.register(sudo_command, metadata=ToolMetadata(tags={ToolTag.PRIVILEGED}))

print(registry.is_enabled("sudo_command"))     # False
print(registry.get_disable_reason("sudo_command"))
# "当前环境不允许特权工具 'sudo_command'"

# 可以注册多个钩子，按注册顺序依次调用
def log_all(tool_name: str, tool, registry) -> None:
    print(f"[钩子] 已注册：{tool_name}")

registry.add_post_register_hook(log_all)
```

## 集成点

ToolRegistry 提供以下集成点：

- **OpenAPI 服务**：自动 REST API 工具生成
- **MCP 服务器**：模型上下文协议工具发现
- **LangChain 工具**：LangChain 生态系统集成
- **原生 Python**：直接类和函数注册

这使其成为在 LLM 应用程序中管理来自不同来源工具的中央枢纽。

## 另请参阅

- [事件](../events.md) - `ChangeEvent`、`ChangeEventType` 和 `ChangeCallback` 的详细文档
