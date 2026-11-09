---
title: 结果大小管理
summary: 大型工具输出的自动截断与持久化
description: 如何配置 max_result_size 与 max_result_tokens、截断策略和结果持久化，防止过大的工具输出占满 LLM 上下文
keywords: 截断, 结果大小, max_result_size, max_result_tokens, 持久化, TruncatedResult
author: Oaklight
---

# 结果大小管理

某些工具会产生大量输出——数据库查询、文件读取、API 响应——可能超出 token 限制并占满 LLM 上下文。ToolRegistry 提供自动结果截断功能，并可选择将完整输出持久化到临时文件。

## 概览

当工具的结果超过大小限制时，ToolRegistry 会：

1. 当注册表启用 `persist_large_results` 时，将**完整结果**存入私有的按运行目录
   （默认关闭）
2. 使用可配置的策略**截断**结果
3. 在前面添加包含原始大小以及（已存储时）不透明结果 id 的头部信息
4. 将截断后的结果返回给 LLM

限制可以按字符（`max_result_size`）或按 token（`max_result_tokens`）给出。
能解析为 JSON 的结果会被结构化裁剪，在裁剪结果未超出限制时仍然可解析；否则按
文本截断，与此前行为一致。其余文本按行边界切分。

## 配置大小限制

### 单工具限制

在 `ToolMetadata` 上设置 `max_result_size`（单位：字符数）：

```python
from toolregistry import Tool, ToolMetadata

def query_database(sql: str) -> str:
    """Execute a SQL query and return results."""
    ...

registry.register(
    Tool.from_function(
        query_database,
        metadata=ToolMetadata(max_result_size=2000),
    )
)
```

### 注册表全局默认值

通过 `ToolRegistry` 设置所有工具的默认限制：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry(default_max_result_size=5000)
```

单工具的 `max_result_size` 优先于注册表默认值。未设置 `max_result_size`（默认 `None`）的工具不受限制，除非注册表设置了默认值。

### Token 预算

`max_result_tokens` 以 token 为单位设置同样的限制：

```python
registry = ToolRegistry(default_max_result_tokens=4000)

# 或按工具设置：
ToolMetadata(max_result_tokens=1000)
```

token 按每 token 4 个字符的固定估算换算为字符
（`toolregistry.llm.truncation.CHARS_PER_TOKEN`）。这是一个数量级保护，而不是
分词器；需要精确截断时请使用 `max_result_size`。工具级取值覆盖该字段的注册表
默认值；字符限制与 token 限制同时存在时，取较小者。

## 截断策略

内容决定机制。能解析为 JSON 的结果无论选择哪种策略都会先做结构化裁剪：对象根会
获得一个 `_truncation` 键，携带 `omitted_items` 与 `omitted_chars`（若该键已存在
则改名）；数组根会追加一个携带相同计数的哨兵元素；文档中过长的字符串会带上自身
的省略计数。只有裁剪结果未超出限制时才会使用这种输出；当元数据在预算内放不下时，
结果回退到下面的文本路径，可能不再可解析，与此前一致。对于其他文本，适用下面的
策略，`HEAD_TAIL` 在结果至少有三行时按行边界切分。

通过 `TruncationStrategy` 提供两种策略：

| 策略 | 行为 |
|------|------|
| `HEAD` | 仅保留前 `max_size` 个字符 |
| `HEAD_TAIL` | 保留首尾部分，中间插入省略标记 **（默认）** |

### HEAD_TAIL（默认）

将预算分配给结果的开头和结尾，在中间插入标记显示省略的字符数：

```
输出的开头部分...
... (truncated 15000 chars) ...
...输出的结尾部分
```

这种方式同时保留了开头（通常是列标题、初始上下文）和结尾（通常是摘要或最终结果）。

### HEAD

简单地在 `max_size` 处截断结果。适用于只需要开头部分的场景。

## 截断输出格式

发生截断时，发送给 LLM 的结果包含元数据头部：

```
[Truncated: 20000 chars -> 2000 chars | full output: res_0123456789ab (read it with read_result)]
输出的开头部分...
... (truncated 18000 chars) ...
...输出的结尾部分
```

完整结果已存储时，头部给出不透明 id，LLM 可以用内置的 `read_result` 工具分页读取
完整输出。头部中永远不会出现文件系统路径。

裁剪结果未超出限制时，JSON 结果保持为 JSON。对象根的元数据随文档一起返回
（计数取决于实际裁剪的内容）：

```json
{"items":[{"value":0},{"value":1}],"_truncation":{"omitted_items":198,"omitted_chars":2970}}
```

## 持久化

持久化是可选项。`ToolRegistry(persist_large_results=True)` 会把每次截断的完整结果
存入私有的按运行目录（目录权限 `0700`，文件权限 `0600`）。头部携带不透明 id
（`res_<12 hex>`），内置的 `read_result(id, offset=0, limit=8000)` 工具可分页读取
存储的文本。结果在 24 小时后过期；目录总量上限 64 MiB，超出时按最旧优先淘汰，
刚写入的文件不会被淘汰，即使它本身就超过配额。

不启用该选项时不会写入磁盘：截断结果只包含截断后的文本。

## 编程接口

截断模块也可直接使用：

```python
from toolregistry.llm.truncation import (
    ResultStore,
    TruncationStrategy,
    truncate_result,
)

store = ResultStore(root="/var/tmp/my-results", ttl=3600, quota=32 * 1024 * 1024)
result = truncate_result(
    result_str=very_long_string,
    max_size=2000,
    strategy=TruncationStrategy.HEAD_TAIL,
    tool_name="my_tool",
    persist=True,
    store=store,
)

print(result.truncated)       # True
print(result.original_size)   # 20000
print(result.result_id)       # "res_0123456789ab"
print(result.full_path)       # 宿主路径，仅供程序使用
print(result.content)         # 截断后的内容
print(str(result))            # 头部给出 id，绝不给出路径
```

`truncate_result` 同样执行内容感知规则；需要自行换算 token 预算的调用方可以使用
导出的 `CHARS_PER_TOKEN`。`persist=True` 且未传 `store` 时使用进程级的
`default_result_store()`；传入自己的 `ResultStore` 可指定目录、TTL 与配额。注册表
内置的 `read_result` 只读取该注册表存储的结果，因此直接调用 `truncate_result` 时
必须用同一个 store 读回。

### TruncatedResult 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | （可能截断的）文本内容 |
| `original_size` | `int` | 原始结果大小（字符数） |
| `truncated` | `bool` | 是否进行了截断 |
| `full_path` | `str \| None` | 存储结果的宿主路径；`str()` 从不渲染它 |
| `result_id` | `str \| None` | 供 `read_result` 使用的不透明 id；未存储时为 `None` |
