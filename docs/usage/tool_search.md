---
title: 工具搜索
summary: 基于 BM25 稀疏搜索的自然语言工具发现
description: 如何使用 ToolSearchTool 在大型工具注册表中实现动态工具发现，包括延迟加载和搜索提示
keywords: 工具搜索, BM25, 工具发现, 延迟加载, 搜索提示, ToolSearchTool
author: Oaklight
---

# 工具搜索

当注册表包含数十甚至数百个工具时，在初始提示中发送所有工具 schema 会浪费 token 并降低 LLM 性能。**ToolSearchTool** 允许 LLM 通过自然语言查询按需发现相关工具，底层使用 BM25F（带字段加权的最佳匹配 25）稀疏搜索。

???+ note "更新日志"
    新增于：[#108](../../pull/108)（Unreleased）

## 概览

```mermaid
flowchart LR
    LLM -- "search('压缩文件')" --> ToolSearchTool
    ToolSearchTool -- "BM25F 索引" --> Results["[{name, description, score, ...}]"]
    Results --> LLM
    LLM -- "call compress_file(...)" --> Registry
```

ToolSearchTool 为每个工具索引五个字段，支持可配置权重：

| 字段 | 默认权重 | 来源 |
|------|---------|------|
| `name` | 3.0 | 工具名称（下划线转空格） |
| `description` | 2.0 | 工具文档字符串 / 描述 |
| `search_hint` | 2.0 | `ToolMetadata.search_hint` |
| `tags` | 1.5 | `ToolMetadata.tags` + `custom_tags` |
| `params` | 1.0 | JSON schema 中的参数名 |

## 快速开始

```python
from toolregistry import ToolRegistry, ToolSearchTool

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@registry.register
def read_file(path: str) -> str:
    """Read the contents of a file from the filesystem."""
    return open(path).read()

# 在注册表上创建搜索器
searcher = ToolSearchTool(registry)

# 自然语言搜索
results = searcher.search("read text file")
print(results[0]["name"])   # "read_file"
print(results[0]["score"])  # 1.23 (BM25 分数)
```

## 搜索结果

每个结果是一个包含以下键的字典：

| 键 | 类型 | 说明 |
|----|------|------|
| `name` | `str` | 工具名称（标识符） |
| `description` | `str` | 工具描述 |
| `score` | `float` | BM25 相关性分数（越高越相关） |
| `namespace` | `str \| None` | 工具命名空间（如有） |
| `deferred` | `bool` | 工具是否标记为延迟加载 |

```python
results = searcher.search("email", top_k=3)
for r in results:
    print(f"{r['name']}: {r['score']:.2f} — {r['description']}")
```

## 延迟加载工具

使用 `ToolMetadata(defer=True)` 标记工具，将其从初始提示中排除。这些工具仍可通过 ToolSearchTool 被搜索到：

```python
from toolregistry import Tool, ToolMetadata, ToolTag

def compress_file(path: str) -> str:
    """Compress a file into a zip archive."""
    ...

registry.register(
    Tool.from_function(
        compress_file,
        metadata=ToolMetadata(
            defer=True,  # 从初始 get_schemas() 中排除
            tags={ToolTag.FILE_SYSTEM},
        ),
    )
)

# 延迟加载的工具仍可被发现
results = searcher.search("compress zip")
assert results[0]["name"] == "compress_file"
assert results[0]["deferred"] is True
```

!!! info "后续计划"
    框架级别的自动 schema 注入（当 LLM 发现延迟工具时动态将其 schema 添加到提示中）已在规划中，但尚未实现。

## 搜索提示

使用 `ToolMetadata.search_hint` 添加同义词、相关概念或领域特定术语，以提高工具的可发现性：

```python
registry.register(
    Tool.from_function(
        read_file,
        metadata=ToolMetadata(
            search_hint="open load text content cat",
        ),
    )
)
```

`search_hint` 字段的索引权重为 2.0（与 `description` 相同），因此这些关键词对排名的影响与工具自身描述一样强。

## 自定义字段权重

覆盖默认 BM25F 字段权重以调整排名策略：

```python
searcher = ToolSearchTool(
    registry,
    field_weights={
        "name": 5.0,          # 提高精确名称匹配权重
        "description": 1.0,
        "tags": 3.0,          # 提高基于标签的发现权重
        "params": 0.5,
        "search_hint": 2.0,
    },
)
```

## 重建索引

索引在构造时一次性构建。修改注册表（添加、删除或更新工具）后，需调用 `rebuild_index()`：

```python
@registry.register
def new_tool(x: int) -> int:
    """A newly added tool."""
    return x * 2

searcher.rebuild_index()

results = searcher.search("newly added")
assert results[0]["name"] == "new_tool"
```

!!! tip
    通过 ChangeCallback 自动更新索引已在规划中。目前请在修改注册表后手动调用 `rebuild_index()`。

## 实现细节

ToolSearchTool 使用 [zerodep](https://pypi.org/project/zerodep/) 的 `SparseIndex`（v0.2.2）的内置副本——一个纯 Python BM25/BM25F 实现，**零外部依赖**。索引完全存储在内存中，大小通常可忽略不计（100 个工具 ≈ 几 KB）。

BM25F 参数：

- `k1 = 1.5` — 词频饱和度
- `b = 0.75` — 文档长度归一化
- `delta = 1.0` — BM25+ 下限修正
