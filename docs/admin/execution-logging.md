# 执行日志

管理面板与 ToolRegistry 的执行日志功能集成，提供工具使用的详细洞察。

## 启用执行日志

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

# 启用日志，自定义缓冲区大小
log = registry.enable_logging(max_entries=1000)

# 注册并使用工具...
@registry.register
def calculator_add(a: int, b: int) -> int:
    return a + b

# 启用管理面板以查看日志
info = registry.enable_admin()
```

### 脱敏与留存

默认情况下，日志可以安全地通过管理面板暴露：

- 名称表示凭据的键（`password`、`token`、`secret`、`api_key`、
  `authorization`、`credential` 等，任意嵌套层级）的值会被替换为
  `***REDACTED***`。
- `arguments` 或 `result` 的 JSON 编码超过 2000 个字符时，会被替换为
  `{"truncated": true, "size": ..., "preview": ...}`。
- 追溯信息会被丢弃；`exception_type` 与 `error` 保留异常类型和消息。

传入 `full_record=True` 可保留原始参数、结果与追溯信息。仅在日志不会被
不受信任的调用方访问时使用：

```python
log = registry.enable_logging(max_entries=1000, full_record=True)
```

## 日志条目结构

每个执行日志条目包含：

| 字段 | 类型 | 描述 |
|------|------|------|
| `id` | `str` | 唯一标识符（UUID） |
| `tool_name` | `str` | 执行的工具名称 |
| `timestamp` | `datetime` | 执行发生的时间 |
| `status` | `ExecutionStatus` | `success`、`error`、`timeout` 或 `disabled` |
| `duration_ms` | `float` | 执行耗时（毫秒） |
| `arguments` | `dict` | 传递给工具的输入参数 |
| `result` | `Any` | 执行结果（成功执行时） |
| `error` | `str \| None` | 错误信息（失败执行时） |
| `exception_type` | `str \| None` | 异常类的限定名称，如 `"ValueError"` |
| `traceback` | `str \| None` | 异常的格式化追溯字符串（默认丢弃；`full_record=True` 时保留） |
| `metadata` | `dict` | 附加元数据 |

## 编程方式查询日志

```python
# 获取执行日志实例
log = registry.get_execution_log()

if log:
    # 获取最近的条目
    entries = log.get_entries(limit=10)

    # 按工具名称过滤
    calc_entries = log.get_entries(tool_name="calculator_add")

    # 按状态过滤
    from toolregistry.admin import ExecutionStatus
    errors = log.get_entries(status=ExecutionStatus.ERROR)

    # 获取统计信息
    stats = log.get_stats()
    print(f"总执行次数: {stats['total_entries']}")
    print(f"平均耗时: {stats['avg_duration_ms']:.2f}ms")
```
