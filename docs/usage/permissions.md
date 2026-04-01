# 权限系统

ToolRegistry 提供了内置的权限系统，允许您控制哪些工具调用被允许、拒绝或需要在执行前进行明确确认。该系统围绕三个概念设计：**规则**、**策略**和**处理器**。

## 概述

权限系统在 `execute_tool_calls()` 期间进行评估。当工具调用到达时，权限策略按顺序检查每条规则（首次匹配即生效）。根据匹配规则的结果，调用会被：

- **允许**（`ALLOW`）-- 工具正常执行。
- **拒绝**（`DENY`）-- 工具调用被拒绝并返回错误消息。
- **上报**（`ASK`）-- 咨询权限处理器以做出最终决定。

如果未配置策略，默认允许所有工具调用。

## 快速开始

```python
from toolregistry import (
    ToolRegistry,
    PermissionPolicy,
    PermissionRule,
    PermissionResult,
)

registry = ToolRegistry()

# 注册一些工具
@registry.register
def read_file(path: str) -> str:
    """从磁盘读取文件。"""
    return open(path).read()

@registry.register
def delete_file(path: str) -> str:
    """从磁盘删除文件。"""
    import os
    os.remove(path)
    return f"Deleted {path}"

# 定义权限策略
policy = PermissionPolicy(
    rules=[
        PermissionRule(
            name="allow_read",
            match=lambda tool, params: tool.name == "read_file",
            result=PermissionResult.ALLOW,
            reason="读取文件是安全的",
        ),
        PermissionRule(
            name="block_delete",
            match=lambda tool, params: tool.name == "delete_file",
            result=PermissionResult.DENY,
            reason="不允许删除文件",
        ),
    ],
    fallback=PermissionResult.DENY,
)

registry.set_permission_policy(policy)
```

使用此策略，`read_file` 调用正常执行，而 `delete_file` 调用将被拒绝。

## 核心概念

### PermissionResult

表示权限检查结果的三态枚举：

| 值 | 描述 |
|-------|-------------|
| `ALLOW` | 允许工具调用 |
| `DENY` | 拒绝工具调用 |
| `ASK` | 将决定委派给处理器 |

### PermissionRule

将匹配谓词映射到结果的单条规则。规则按顺序评估；第一条 `match` 返回 `True` 的规则决定结果。

```python
from toolregistry import PermissionRule, PermissionResult

rule = PermissionRule(
    name="ask_for_network_tools",
    match=lambda tool, params: "http" in str(params),
    result=PermissionResult.ASK,
    reason="工具调用涉及网络访问",
)
```

**属性：**

| 属性 | 类型 | 描述 |
|-----------|------|-------------|
| `name` | `str` | 规则的可读标识符 |
| `match` | `Callable[[Tool, dict], bool]` | 接收 `(tool, parameters)` 的谓词 |
| `result` | `PermissionResult` | 规则匹配时的决定 |
| `reason` | `str` | 在 `PermissionRequest` 中展示的说明 |

### PermissionPolicy

包含有序规则集合和回退结果的策略。

```python
from toolregistry import PermissionPolicy, PermissionResult

policy = PermissionPolicy(
    rules=[rule_1, rule_2, rule_3],
    fallback=PermissionResult.DENY,  # 默认安全
    handler=my_handler,  # 可选的策略级处理器
)
```

**评估语义：** 规则按列表顺序检查。第一条 `match` 返回 `True` 的规则产生最终决定。如果没有规则匹配，使用 `fallback` 结果。

**属性：**

| 属性 | 类型 | 描述 |
|-----------|------|-------------|
| `rules` | `list[PermissionRule]` | 有序规则列表 |
| `fallback` | `PermissionResult` | 无规则匹配时的结果（默认：`DENY`） |
| `handler` | `PermissionHandler \| None` | 可选的策略级 `ASK` 结果处理器 |

## 结合工具标签使用权限

权限系统与 `ToolTag` 和 `ToolMetadata` 配合良好。您可以为工具打标签，并编写基于标签匹配的规则（而不是工具名称），使策略更易维护。

### ToolTag

常见工具特征的预定义标签：

| 标签 | 描述 |
|-----|-------------|
| `READ_ONLY` | 工具仅读取数据 |
| `DESTRUCTIVE` | 工具修改或删除数据 |
| `NETWORK` | 工具需要网络访问 |
| `FILE_SYSTEM` | 工具访问文件系统 |
| `SLOW` | 工具可能耗时较长 |
| `PRIVILEGED` | 工具需要提升权限 |

### ToolMetadata 字段

除标签外，`ToolMetadata` 还提供执行提示：

| 字段 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `tags` | `set[ToolTag]` | `set()` | 预定义分类标签 |
| `custom_tags` | `set[str]` | `set()` | 用户自定义标签 |
| `timeout` | `float \| None` | `None` | 单次调用超时（秒） |
| `is_concurrency_safe` | `bool` | `True` | 工具是否可并发运行 |
| `locality` | `"local" \| "remote" \| "any"` | `"any"` | 工具执行位置（本地、远程或任意） |

### 为工具打标签

```python
from toolregistry import Tool, ToolMetadata, ToolTag

tool = Tool.from_function(
    my_function,
    metadata=ToolMetadata(
        tags={ToolTag.NETWORK, ToolTag.SLOW},
        custom_tags={"requires_api_key"},
        timeout=30.0,
        locality="remote",
    ),
)
registry.register(tool)
```

### 内置规则

ToolRegistry 提供了基于 `ToolTag` 值匹配的预构建规则：

```python
from toolregistry.permissions.builtin_rules import (
    ALLOW_READONLY,     # 允许标记为 READ_ONLY 的工具
    ASK_DESTRUCTIVE,    # 对标记为 DESTRUCTIVE 的工具请求确认
    DENY_PRIVILEGED,    # 拒绝标记为 PRIVILEGED 的工具
    ASK_NETWORK,        # 对标记为 NETWORK 的工具请求确认
    ASK_FILE_SYSTEM,    # 对标记为 FILE_SYSTEM 的工具请求确认
)

policy = PermissionPolicy(
    rules=[
        ALLOW_READONLY,
        DENY_PRIVILEGED,
        ASK_DESTRUCTIVE,
        ASK_NETWORK,
        ASK_FILE_SYSTEM,
    ],
    fallback=PermissionResult.DENY,
)

registry.set_permission_policy(policy)
```

## 权限处理器

当规则返回 `ASK` 时，系统将决定委派给权限处理器。处理器实现一个简单的协议：

### 同步处理器

```python
from toolregistry import PermissionHandler, PermissionRequest, PermissionResult

class CLIPermissionHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        print(f"工具：{request.tool_name}")
        print(f"原因：{request.reason}")
        print(f"参数：{request.parameters}")
        answer = input("允许此调用？[y/N] ")
        return PermissionResult.ALLOW if answer.lower() == "y" else PermissionResult.DENY
```

### 异步处理器

```python
from toolregistry import AsyncPermissionHandler, PermissionRequest, PermissionResult

class WebSocketPermissionHandler:
    async def handle(self, request: PermissionRequest) -> PermissionResult:
        response = await ws.ask_user(request.tool_name, request.reason)
        return PermissionResult.ALLOW if response == "yes" else PermissionResult.DENY
```

### PermissionRequest

当规则返回 `ASK` 时传递给处理器的上下文对象：

| 属性 | 类型 | 描述 |
|-----------|------|-------------|
| `tool_name` | `str` | 被调用工具的名称 |
| `parameters` | `dict[str, Any]` | 调用者打算传递的参数 |
| `reason` | `str` | 匹配规则中的说明 |
| `rule_name` | `str` | 触发 `ASK` 的规则名称 |
| `metadata` | `ToolMetadata` | 工具的元数据，供处理器参考 |

### 注册处理器

处理器可以在两个层级注册：

1. **注册表级别** -- 适用于所有策略：

    ```python
    registry.set_permission_handler(
        CLIPermissionHandler(),
        fallback=PermissionResult.DENY,
    )
    ```

2. **策略级别** -- 优先于注册表级别的处理器：

    ```python
    policy = PermissionPolicy(
        rules=[...],
        handler=WebSocketPermissionHandler(),
    )
    ```

**`ASK` 结果的解析顺序：**

1. 策略级处理器
2. 注册表级处理器
3. 回退结果（默认为 `DENY`）

## 运行时管理权限

```python
# 设置策略
registry.set_permission_policy(policy)

# 获取当前策略
current_policy = registry.get_permission_policy()

# 移除策略（允许所有调用）
registry.remove_permission_policy()

# 设置处理器
registry.set_permission_handler(handler)

# 获取当前处理器
current_handler = registry.get_permission_handler()

# 移除处理器
registry.remove_permission_handler()
```

## 权限事件

权限系统会发出变更事件，可通过[回调机制](../api/events.md)进行观察：

| 事件类型 | 触发时机 |
|------------|------|
| `PERMISSION_DENIED` | 工具调用被策略拒绝 |
| `PERMISSION_ASKED` | 工具调用被上报给处理器 |

```python
from toolregistry import ChangeEvent, ChangeEventType

def permission_monitor(event: ChangeEvent) -> None:
    if event.event_type == ChangeEventType.PERMISSION_DENIED:
        print(f"已拒绝：{event.tool_name} - {event.reason}")
    elif event.event_type == ChangeEventType.PERMISSION_ASKED:
        print(f"已上报：{event.tool_name} - {event.reason}")

registry.on_change(permission_monitor)
```

## 完整示例

```python
from toolregistry import (
    ToolRegistry,
    ToolMetadata,
    ToolTag,
    PermissionPolicy,
    PermissionResult,
    PermissionRequest,
)
from toolregistry.permissions.builtin_rules import (
    ALLOW_READONLY,
    ASK_DESTRUCTIVE,
    DENY_PRIVILEGED,
)

registry = ToolRegistry()

# 注册带元数据的工具
from toolregistry import Tool

def search_db(query: str) -> str:
    """搜索数据库。"""
    return f"Results for: {query}"

def drop_table(name: str) -> str:
    """删除数据库表。"""
    return f"Dropped {name}"

registry.register(
    Tool.from_function(
        search_db,
        metadata=ToolMetadata(tags={ToolTag.READ_ONLY}),
    )
)
registry.register(
    Tool.from_function(
        drop_table,
        metadata=ToolMetadata(tags={ToolTag.DESTRUCTIVE}),
    )
)

# 创建处理器
class SimpleHandler:
    def handle(self, request: PermissionRequest) -> PermissionResult:
        print(f"[权限] {request.tool_name}：{request.reason}")
        return PermissionResult.DENY  # 本示例中默认拒绝

# 设置策略和处理器
policy = PermissionPolicy(
    rules=[ALLOW_READONLY, ASK_DESTRUCTIVE],
    fallback=PermissionResult.DENY,
)
registry.set_permission_policy(policy)
registry.set_permission_handler(SimpleHandler())

# search_db 将被允许（READ_ONLY 标签匹配 ALLOW_READONLY）
# drop_table 将被上报给处理器（DESTRUCTIVE 标签匹配 ASK_DESTRUCTIVE）
```

## 参见

- [权限 API 参考](../api/permissions.md) -- `PermissionPolicy`、`PermissionRule`、`PermissionResult`、`PermissionHandler` 类详情
- [执行模式](concurrency_modes.md) -- 通过 `ToolMetadata` 设置超时和并发安全性
