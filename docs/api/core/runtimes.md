# Runtimes

The `toolregistry.runtimes` subpackage provides the **PTC (Programmatic Tool Calling)** protocols and types. It allows LLMs to write Python code that calls tools programmatically, reducing round-trips and token consumption.

!!! note "Zero toolregistry imports"
    This subpackage has no imports from toolregistry internals. It operates
    exclusively on callables, dicts, and its own protocol types — same
    constraint as `executor/`.

## CodeResult

Structured result from code execution.

```python
from toolregistry.runtimes import CodeResult

result = CodeResult(
    stdout="42\n",
    stderr="",
    return_code=0,
    error=None,
)
```

| Field | Type | Description |
|-------|------|-------------|
| `stdout` | `str` | Captured standard output |
| `stderr` | `str` | Content written to stderr during execution |
| `return_code` | `int` | `0` = success, `1` = exception |
| `error` | `str \| None` | Exception traceback, or `None` if clean exit |

`CodeResult` is a frozen dataclass — instances are immutable.

## ToolProjection

Protocol defining how a tool appears inside a code runtime's namespace.

```python
from toolregistry.runtimes import ToolProjection

class MyProjection:
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def doc(self) -> str | None:
        return "Does something useful."

    def __call__(self, **kwargs):
        return do_something(**kwargs)

assert isinstance(MyProjection(), ToolProjection)  # True
```

| Member | Description |
|--------|-------------|
| `name` (property) | Tool name in the code namespace |
| `doc` (property) | Docstring for introspection |
| `__call__(**kwargs)` | Invoke the tool synchronously |

## DirectProjection

In-process `ToolProjection` implementation. Wraps a bare callable with zero overhead.

```python
from toolregistry.runtimes import DirectProjection

def add(a: int, b: int) -> int:
    return a + b

proj = DirectProjection(name="add", fn=add, doc="Add two numbers.")
proj(a=3, b=4)  # → 7

# From a Tool object:
proj = DirectProjection(name=tool.name, fn=tool.fn, doc=tool.description)
```

- Sync callables are called directly.
- Async callables are dispatched via `asyncio.run()`.

!!! warning "asyncio.run() nesting"
    `DirectProjection.__call__` uses `asyncio.run()` for async callables.
    This cannot be called from within a running event loop. If your
    `CodeRuntime.execute()` runs inside an event loop, it must handle
    this — e.g. by running `exec()` in a separate thread.

## CodeRuntime

Protocol for code execution engines. Accepts code strings with a tool namespace and returns structured results.

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
        # Execute code with tools available...
        ...

assert isinstance(MyRuntime(), CodeRuntime)  # True
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `code` | `str` | Python source code to execute |
| `namespace` | `dict[str, ToolProjection]` | Tools injected into execution namespace |
| `timeout` | `float \| None` | Max wall-clock seconds. `None` = no limit |
| `extra_globals` | `dict[str, Any] \| None` | Non-tool objects (imports, constants). Tool entries win on collision |

## validate_namespace

Helper to check that namespace keys match their `ToolProjection.name`.

```python
from toolregistry.runtimes import DirectProjection, validate_namespace

ns = {
    "add": DirectProjection(name="add", fn=lambda a, b: a + b),
    "mul": DirectProjection(name="mul", fn=lambda a, b: a * b),
}
validate_namespace(ns)  # OK

ns_bad = {"wrong": DirectProjection(name="add", fn=lambda a, b: a + b)}
validate_namespace(ns_bad)  # raises ValueError
```
