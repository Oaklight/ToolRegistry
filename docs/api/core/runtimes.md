# 运行时

`toolregistry.runtimes` 子包提供 **PTC（Programmatic Tool Calling，程序化工具调用）** 的协议和类型。它允许 LLM 编写 Python 代码直接调用工具，减少往返和 token 消耗。

!!! note "零 toolregistry 导入"
    此子包不导入任何 toolregistry 内部模块。它仅使用 callable、dict 和
    自身的协议类型——与 `executor/` 遵循相同的约束。

## CodeResult

代码执行的结构化结果。

```python
from toolregistry.runtimes import CodeResult

result = CodeResult(
    stdout="42\n",
    stderr="",
    return_code=0,
    error=None,
)
```

| 字段 | 类型 | 描述 |
|------|------|------|
| `stdout` | `str` | 捕获的标准输出 |
| `stderr` | `str` | 执行过程中写入 stderr 的内容 |
| `return_code` | `int` | `0` = 成功，`1` = 异常 |
| `error` | `str \| None` | 异常回溯信息，成功时为 `None` |

`CodeResult` 是冻结的 dataclass——实例不可变。

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
| `doc`（属性） | 用于内省的文档字符串 |
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

!!! warning "asyncio.run() 嵌套"
    `DirectProjection.__call__` 对异步 callable 使用 `asyncio.run()`。
    这不能在运行中的事件循环内调用。如果 `CodeRuntime.execute()` 在
    事件循环内运行，必须处理此问题——例如通过 `asyncio.to_thread()` 在
    单独的线程中运行 `exec()`。

## CodeRuntime

代码执行引擎的协议。接受代码字符串和工具命名空间，返回结构化结果。

```python
from toolregistry.runtimes import CodeRuntime, CodeResult, ToolProjection

class MyRuntime:
    async def execute(
        self,
        code: str,
        namespace: dict[str, ToolProjection],
        *,
        timeout: float | None = None,
        extra_globals: dict[str, Any] | None = None,
    ) -> CodeResult:
        # 使用可用工具执行代码...
        ...

assert isinstance(MyRuntime(), CodeRuntime)  # True
```

| 参数 | 类型 | 描述 |
|------|------|------|
| `code` | `str` | 要执行的 Python 源代码 |
| `namespace` | `dict[str, ToolProjection]` | 注入执行命名空间的工具 |
| `timeout` | `float \| None` | 最大执行时间（秒），`None` = 无限制 |
| `extra_globals` | `dict[str, Any] \| None` | 非工具对象（导入、常量等），名称冲突时工具优先 |

## validate_namespace

检查命名空间键是否与 `ToolProjection.name` 匹配的辅助函数。

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
