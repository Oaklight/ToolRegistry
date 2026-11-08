# 源持久化钩子

管理面板可以预览并注册来源，但它不拥有配置文件：注册只影响当前进程。若下游服务拥有配置文件，可安装**源持久化钩子**。面板会把每次来源变更交给它，报告持久化结果，并暴露它维护的按来源状态。

未安装钩子时行为不变：注册与 `GET /api/sources` 的响应结构保持原样。

## 钩子

钩子是包含三个方法的对象，通过 `AdminServer` 或 `enable_admin` 的 `source_hook` 传入：

```python
from toolregistry import AdminServer, ToolRegistry


class ConfigHook:
    def __init__(self, manager):
        self.manager = manager

    def persist(self, change):
        # 存储变更，并返回该来源的状态记录。
        return self.manager.apply(change).to_dict()

    def writable(self):
        return self.manager.config_path is not None

    def statuses(self):
        return self.manager.to_dicts()


server = AdminServer(
    ToolRegistry(),
    port=8081,
    source_hook=ConfigHook(manager),
)
```

| 方法 | 契约 |
|------|------|
| `persist(change)` | 存储变更并返回其状态记录。无法存储时抛出 `SourcePersistenceError`；消息会展示给运维者。 |
| `writable()` | 底层配置是否可写。 |
| `statuses()` | 每个来源的状态记录，包含没有工具的成功、排除与失败来源。 |

`persist` 返回的记录以及 `statuses` 中的每条记录至少包含 `id`、`kind`、`detail`、`namespace`、`status`、`last_error` 与 `names`。`status` 为 `applied`、`excluded` 或 `failed`。`detail` 与 `last_error` 必须脱敏：面板会展示它们。

## 变更对象

`persist` 收到一个 `SourceChange`：

| 字段 | 含义 |
|------|------|
| `action` | `add`、`remove` 或 `replace`。管理面板只发出 `add`；remove 与 replace 来自自行管理来源差异的下游调用方。 |
| `kind` | `openapi`、`mcp` 或 `python`。 |
| `payload` | 提交给面板的来源声明，可能包含凭据。 |
| `namespace` | 请求的命名空间，或 `None`。 |
| `selected` | 运维者保留的工具名，或 `None` 表示全部。 |
| `source_id` | remove 与 replace 使用的现有来源 id；add 为 `None`。 |

`payload` 可能带有认证令牌、请求头、`env` 值或命令参数。钩子不得记录或回显它，并且展示时必须脱敏。面板自身从不记录 `payload`。

## 注册响应

安装钩子后，成功注册会多出两个字段：

```json
{
  "kind": "python",
  "registered": ["isleap"],
  "count": 1,
  "persisted": true,
  "source": {"id": "src_0123456789abcdef", "status": "applied", "...": "..."}
}
```

`source` 即 `persist` 返回的记录，客户端由此得知刚注册来源的 id。

`persist` 失败时注册本身已经成功——工具已生效——因此响应仍为 `200` 并报告失败，而不是声称注册失败：

```json
{
  "kind": "python",
  "registered": ["isleap"],
  "count": 1,
  "persisted": false,
  "persist_error": "configuration is read-only"
}
```

只有什么都没生效时才使用 `5xx`。

## 来源列表

安装钩子后，`GET /api/sources` 的 `sources` 数组保持原样，并增加两个同级字段：

```json
{
  "sources": [{"type": "python", "detail": "calendar", "...": "..."}],
  "source_status": [
    {"id": "src_0123456789abcdef", "kind": "python", "status": "applied", "...": "..."},
    {"id": "src_fedcba9876543210", "kind": "mcp", "status": "failed", "last_error": "...", "...": "..."}
  ],
  "config_writable": true
}
```

`source_status` 原样透传，因此没有注册工具的失败或排除来源仍然可见。可用记录中的 `id` 与 `sources` 关联；没有 id 时按 `kind`/`detail`/`namespace` 关联。内置的来源页只读取 `sources`，安装钩子不会改变它的行为。

`statuses()` 或 `writable()` 抛出异常不会破坏列表：记录日志后，`source_status` 为空、`config_writable` 为 `false`。

## 失败行为

- **持久化失败不会回滚工具。** registry 已经变更；响应报告 `persisted: false` 与实际生效的名称，客户端可只重试写入而无需重新注册。
- **状态失败只降级列表，不影响面板。** 由工具推导出的 `sources` 数组照常提供。
- **钩子是受信代码。** 它在面板进程内运行，能看到包含凭据的完整声明。只安装你信任的钩子。
