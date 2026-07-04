# Programmatic Tool Calling (PTC)

PTC lets LLMs write Python code that orchestrates multiple tool calls in a single code block, reducing round-trips and token consumption.

## Quick start

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.register(search)
registry.register(summarize)
registry.ptc.enable()  # registers "programmatic_tool_call" tool

# Now the LLM can generate tool_use("programmatic_tool_call", {code: "..."})
```

## How it works

```
LLM: tool_use("programmatic_tool_call", {code: "..."})
  → CodeExecutionTool.execute(code)
    → Subprocess: exec(code, {search: stub, summarize: stub})
      → search(query="weather")
        → IPC → main process → registry.invoke("search", {...})
        → result back via IPC
      → summarize(data)
        → IPC → main process → registry.invoke("summarize", {...})
        → result back via IPC
      → print(final_output)
    → return stdout to LLM
```

**Key points:**

- Code runs in an **isolated subprocess** — crashes don't affect the main process
- Tool calls go through `registry.invoke()` — **permissions and logging are enforced**
- Only `print()` output is returned to the LLM — intermediate results stay in variables
- AST validation blocks dangerous code (file I/O, network, unsafe imports)

## Example: multi-tool orchestration

Without PTC (3 round-trips):

```
Turn 1: LLM → tool_use("search", {query: "..."})     → result
Turn 2: LLM → tool_use("filter", {data: result, ...}) → filtered
Turn 3: LLM → tool_use("summarize", {data: filtered}) → summary
```

With PTC (1 round-trip):

```python
# LLM generates this code:
data = search(query="climate change")
filtered = [item for item in data if item["year"] >= 2024]
summary = summarize(data=filtered)
print(f"Found {len(filtered)} recent articles.\n{summary}")
```

## Safety model

| Layer | Protection |
|-------|-----------|
| **AST validation** | Blocks `import os`, `open()`, `eval()`, `subprocess`, network access, etc. |
| **Subprocess isolation** | Code runs in a fresh process — segfaults, OOM, infinite loops are contained |
| **Permission enforcement** | Tool calls go through `registry.invoke()` with full permission checks |
| **Namespace restriction** | Only registered tools are available — no access to registry internals |

## Invocation tracking

Each PTC execution generates a `tr_ptc_` invocation ID shared by all tool calls within that execution:

```python
registry.enable_logging()
registry.ptc.enable()

tool = registry.get_tool("programmatic_tool_call")
tool.run({"code": "print(add(a=1, b=2))"})

# Get the invocation ID
# registry.ptc.last_invocation_id
inv_id = registry.ptc.last_invocation_id  # "tr_ptc_a1b2c3d4"

# Query all tool calls from this execution
log = registry.get_execution_log()
entries = log.get_entries(invocation_id=inv_id)
```

## Configuration

```python
# Custom timeout (default: 30 seconds)
registry.ptc.enable(timeout=60)

# Disable when not needed
registry.ptc.disable()
```

## Requirements

PTC requires the `codecell` package:

```bash
pip install toolregistry[ptc]
```

## What PTC cannot do

- **Call tools not registered in the registry** — only namespace-injected tools are available
- **Persist state between executions** — each `execute()` runs in a fresh subprocess
- **Access files or network directly** — all I/O must go through registered tools
- **Import arbitrary Python packages** — only [safe computation modules](https://github.com/Oaklight/codecell#validators) are allowed
