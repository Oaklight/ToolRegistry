# 运行时 (PTC)

`toolregistry.runtimes` 子包提供 **PTC（Programmatic Tool Calling，程序化工具调用）** 桥接层。它将 toolregistry 的 `Tool` 模型连接到 [`codecell`](https://pypi.org/project/codecell/) 代码执行引擎。

!!! note "零 toolregistry 导入"
    此子包不导入任何 toolregistry 内部模块——与 `executor/` 遵循相同的约束。

!!! tip "代码执行类型"
    `CodeResult`、`SubprocessRuntime`、`IpcSubprocessRuntime` 和验证器由
    `codecell` 包提供：`pip install toolregistry[ptc]`

## CodeExecutionTool

内置 PTC 元工具，让 LLM 编写 Python 代码并在命名空间中调用已注册的工具。通过 `registry.ptc.enable()` 注册。

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.register(search)
registry.register(summarize)
registry.ptc.enable()

# LLM 现在可以生成：
# tool_use("programmatic_tool_call", {
#     "code": "data = search(query='weather')\nprint(summarize(data))"
# })
```

**工作原理：**

1. LLM 生成的代码在**隔离子进程**中运行（通过 `codecell.IpcSubprocessRuntime`）
2. 代码中的工具调用通过双向 IPC 转发回**主进程**
3. 工具执行通过 `registry.invoke()` —— 权限和日志均被强制执行
4. 只有 `print()` 输出返回给 LLM

**调用追踪：** 每次 `execute()` 调用生成一个 `tr_ptc_` 调用 ID。该执行中的所有工具调用共享同一个 ID：

```python
# registry.ptc.last_invocation_id
executor.execute("print(add(a=1, b=2))")

# 查询此次执行的所有工具调用：
log = registry.get_execution_log()
entries = log.get_entries(invocation_id=registry.ptc.last_invocation_id)
```

## ToolProjection

定义工具在代码运行时命名空间中如何呈现的协议。

```python
from toolregistry.runtimes import ToolProjection

class MyProjection:
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def doc(self) -> str | None:
        return "执行某些操作。"

    def __call__(self, **kwargs):
        return do_something(**kwargs)

assert isinstance(MyProjection(), ToolProjection)  # True
```

| 成员 | 描述 |
|------|------|
| `name`（属性） | 代码命名空间中的工具名称 |
| `doc`（属性） | 用于内省的文档字符串（同时设置 `__doc__`） |
| `__call__(**kwargs)` | 同步调用工具 |

## DirectProjection

进程内 `ToolProjection` 实现。以零开销包装裸 callable。

```python
from toolregistry.runtimes import DirectProjection

def add(a: int, b: int) -> int:
    return a + b

proj = DirectProjection(name="add", fn=add, doc="两数相加。")
proj(a=3, b=4)  # → 7

# 从 Tool 对象构造：
proj = DirectProjection(name=tool.name, fn=tool.fn, doc=tool.description)
```

- 同步 callable 直接调用。
- 异步 callable 通过 `asyncio.run()` 分发。

## 辅助函数

### validate_namespace

检查命名空间键是否与 `ToolProjection.name` 匹配：

```python
from toolregistry.runtimes import DirectProjection, validate_namespace

ns = {
    "add": DirectProjection(name="add", fn=lambda a, b: a + b),
    "mul": DirectProjection(name="mul", fn=lambda a, b: a * b),
}
validate_namespace(ns)  # 正常

ns_bad = {"wrong": DirectProjection(name="add", fn=lambda a, b: a + b)}
validate_namespace(ns_bad)  # 抛出 ValueError
```

### namespace_to_callables

将 `ToolProjection` 命名空间转换为纯 callable dict（供 codecell 使用）。会先调用 `validate_namespace()`。

```python
from toolregistry.runtimes import namespace_to_callables

callables = namespace_to_callables(ns)
# {"add": <callable>, "mul": <callable>}
```
