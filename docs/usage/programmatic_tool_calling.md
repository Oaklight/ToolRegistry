# 程序化工具调用 (PTC)

PTC 让 LLM 编写 Python 代码，在一个代码块中编排多个工具调用，减少往返次数和 token 消耗。

## 快速开始

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()
registry.register(search)
registry.register(summarize)
registry.ptc.enable()  # 注册 "programmatic_tool_call" 工具

# LLM 现在可以生成 tool_use("programmatic_tool_call", {code: "..."})
```

## 工作原理

```
LLM: tool_use("programmatic_tool_call", {code: "..."})
  → CodeExecutionTool.execute(code)
    → 子进程: exec(code, {search: stub, summarize: stub})
      → search(query="weather")
        → IPC → 主进程 → registry.invoke("search", {...})
        → 结果通过 IPC 返回
      → summarize(data)
        → IPC → 主进程 → registry.invoke("summarize", {...})
        → 结果通过 IPC 返回
      → print(final_output)
    → 返回 stdout 给 LLM
```

**关键点：**

- 代码在**隔离子进程**中运行——崩溃不会影响主进程
- 工具调用通过 `registry.invoke()` 执行——**权限和日志均被强制执行**
- 只有 `print()` 输出返回给 LLM——中间结果保留在变量中
- AST 验证阻止危险代码（文件 I/O、网络、不安全的导入）

## 示例：多工具编排

不使用 PTC（3 次往返）：

```
Turn 1: LLM → tool_use("search", {query: "..."})     → result
Turn 2: LLM → tool_use("filter", {data: result, ...}) → filtered
Turn 3: LLM → tool_use("summarize", {data: filtered}) → summary
```

使用 PTC（1 次往返）：

```python
# LLM 生成此代码：
data = search(query="climate change")
filtered = [item for item in data if item["year"] >= 2024]
summary = summarize(data=filtered)
print(f"找到 {len(filtered)} 篇近期文章。\n{summary}")
```

## 安全模型

| 层级 | 保护 |
|------|------|
| **AST 验证** | 阻止 `import os`、`open()`、`eval()`、`subprocess`、网络访问等 |
| **子进程隔离** | 代码在新进程中运行——段错误、OOM、死循环被隔离 |
| **权限强制** | 工具调用通过 `registry.invoke()` 并执行完整权限检查 |
| **命名空间限制** | 只有已注册的工具可用——无法访问 registry 内部 |

## 调用追踪

每次 PTC 执行生成一个 `tr_ptc_` 调用 ID，该执行中的所有工具调用共享此 ID：

```python
registry.enable_logging()
registry.ptc.enable()

tool = registry.get_tool("programmatic_tool_call")
tool.run({"code": "print(add(a=1, b=2))"})

# 获取调用 ID
# registry.ptc.last_invocation_id
inv_id = registry.ptc.last_invocation_id  # "tr_ptc_a1b2c3d4"

# 查询此次执行的所有工具调用
log = registry.get_execution_log()
entries = log.get_entries(invocation_id=inv_id)
```

## 配置

```python
# 自定义超时（默认：30 秒）
registry.ptc.enable(timeout=60)

# 不需要时禁用
registry.ptc.disable()
```

## 依赖

PTC 需要 `codecell` 包：

```bash
pip install toolregistry[ptc]
```

## PTC 的限制

- **无法调用未注册的工具** — 只有命名空间注入的工具可用
- **无法在执行间保持状态** — 每次 `execute()` 在新子进程中运行
- **无法直接访问文件或网络** — 所有 I/O 必须通过已注册的工具
- **无法导入任意 Python 包** — 只允许[安全的计算模块](https://github.com/Oaklight/codecell#validators)
