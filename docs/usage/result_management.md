---
title: 结果大小管理
summary: 大型工具输出的自动截断与持久化
description: 如何配置 max_result_size、截断策略和结果持久化，防止过大的工具输出占满 LLM 上下文
keywords: 截断, 结果大小, max_result_size, 持久化, TruncatedResult
author: Oaklight
---

# 结果大小管理

某些工具会产生大量输出——数据库查询、文件读取、API 响应——可能超出 token 限制并占满 LLM 上下文。ToolRegistry 提供自动结果截断功能，并可选择将完整输出持久化到临时文件。

## 概览

当工具的结果超过大小限制时，ToolRegistry 会：

1. 将**完整结果**写入临时文件（可选，默认启用）
2. 使用可配置的策略**截断**结果
3. 在前面添加包含原始大小和文件路径的头部信息
4. 将截断后的结果返回给 LLM

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

## 截断策略

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
[Truncated: 20000 chars -> 2000 chars | full output: /tmp/toolregistry_results/query_database_1711900000_a1b2c3d4e5f6.txt]
输出的开头部分...
... (truncated 18000 chars) ...
...输出的结尾部分
```

LLM（或用户）可以通过持久化的文件路径访问完整输出。

## 持久化

默认情况下，完整结果在截断前写入 `/tmp/toolregistry_results/` 下的临时文件。文件名包含：

- 工具名称
- Unix 时间戳
- 内容哈希（SHA-256，前 12 位）

示例：`query_database_1711900000_a1b2c3d4e5f6.txt`

## 编程接口

截断模块也可直接使用：

```python
from toolregistry.truncation import truncate_result, TruncationStrategy

result = truncate_result(
    result_str=very_long_string,
    max_size=2000,
    strategy=TruncationStrategy.HEAD_TAIL,
    tool_name="my_tool",
    persist=True,
)

print(result.truncated)       # True
print(result.original_size)   # 20000
print(result.full_path)       # "/tmp/toolregistry_results/..."
print(result.content)         # 截断后的内容
print(str(result))            # 带头部信息的格式化输出
```

### TruncatedResult 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | （可能截断的）文本内容 |
| `original_size` | `int` | 原始结果大小（字符数） |
| `truncated` | `bool` | 是否进行了截断 |
| `full_path` | `str \| None` | 持久化完整结果的文件路径 |
