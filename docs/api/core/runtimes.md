# Runtimes (PTC)

The `toolregistry.runtimes` subpackage provides the **PTC (Programmatic Tool Calling)** bridge layer. It connects toolregistry's `Tool` model to the [`codecell`](https://pypi.org/project/codecell/) code execution engine.

!!! note "Zero toolregistry imports"
    This subpackage has no imports from toolregistry internals — same
    constraint as `executor/`.

!!! tip "Code execution types"
    `CodeResult`, `SubprocessRuntime`, `IpcSubprocessRuntime`, and validators
    are provided by the `codecell` package: `pip install toolregistry[ptc]`

## CodeExecutionTool

Built-in PTC meta-tool that lets LLMs write Python code with registered tools callable in the namespace. Registered via `registry.ptc.enable()`.

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.register(search)
registry.register(summarize)
registry.ptc.enable()

# LLM can now generate:
# tool_use("code_execution", {
#     "code": "data = search(query='weather')\nprint(summarize(data))"
# })
```

**How it works:**

1. LLM-generated code runs in an **isolated subprocess** via `codecell.IpcSubprocessRuntime`
2. Tool calls in the code are forwarded back to the **main process** via bidirectional IPC
3. Tool execution goes through `registry.invoke()` — permissions and logging are enforced
4. Only `print()` output is returned to the LLM

**Invocation tracking:** Each `execute()` call generates a `tr_ptc_` invocation ID. All tool calls within that execution share the same ID in the execution log:

```python
# registry.ptc.last_invocation_id
executor.execute("print(add(a=1, b=2))")

# Query all tool calls from this execution:
log = registry.get_execution_log()
entries = log.get_entries(invocation_id=registry.ptc.last_invocation_id)
```

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
| `doc` (property) | Docstring for introspection (also sets `__doc__`) |
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

## Helper functions

### validate_namespace

Check that namespace keys match their `ToolProjection.name`:

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

### namespace_to_callables

Convert a `ToolProjection` namespace to a plain callable dict for codecell. Calls `validate_namespace()` first.

```python
from toolregistry.runtimes import namespace_to_callables

callables = namespace_to_callables(ns)
# {"add": <callable>, "mul": <callable>}
```
