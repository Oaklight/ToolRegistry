---
title: 工具发现
summary: 基于 BM25 稀疏搜索的渐进式工具发现
description: 如何使用 ToolDiscoveryTool 在大型工具注册表中实现动态工具发现，包括延迟加载、延迟摘要和搜索提示
keywords: 工具发现, BM25, 渐进式披露, 延迟加载, 搜索提示, ToolDiscoveryTool
author: Oaklight
---

# 工具发现

当注册表包含数十甚至数百个工具时，在初始提示中发送所有工具 schema 会浪费 token 并降低 LLM 性能。**ToolDiscoveryTool** 允许 LLM 通过精确名称查找或自然语言查询按需发现相关工具，底层使用 BM25F（带字段加权的最佳匹配 25）稀疏搜索。

???+ note "更新日志"
    新增于：[#108](../../pull/108)（Unreleased）
    更新于：[#114](../../pull/114) — `enable_tool_search()`、`include_deferred`、搜索结果包含 schema
    更新于：[#118](../../pull/118) — 重命名为 `ToolDiscoveryTool` / `discover_tools`，新增精确匹配、`get_deferred_summaries()`

## 概览

```mermaid
flowchart LR
    LLM -- "discover('compress_file')" --> ToolDiscoveryTool
    ToolDiscoveryTool -- "精确匹配" --> ExactResult["[{name, schema, score: 1.0}]"]
    LLM -- "discover('压缩文件')" --> ToolDiscoveryTool
    ToolDiscoveryTool -- "BM25F 索引" --> FuzzyResults["[{name, description, score, ...}]"]
```

ToolDiscoveryTool 支持两种模式：

1. **精确匹配** — 如果查询与已注册工具名完全匹配，立即返回完整 schema（score 1.0）。
2. **模糊搜索** — 否则执行 BM25F 多字段搜索。

为每个工具索引五个字段，支持可配置权重：

| 字段 | 默认权重 | 来源 |
|------|---------|------|
| `name` | 3.0 | 工具名称（下划线转空格） |
| `description` | 2.0 | 工具文档字符串 / 描述 |
| `search_hint` | 2.0 | `ToolMetadata.search_hint` |
| `tags` | 1.5 | `ToolMetadata.tags` + `custom_tags` |
| `params` | 1.0 | JSON schema 中的参数名 |

## 快速开始

最简单的启用方式是通过 `enable_tool_discovery()`，它会将 `discover_tools` 注册为 registry 中的可调用工具，让 LLM 可以自主发现工具：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

@registry.register
def read_file(path: str) -> str:
    """Read the contents of a file from the filesystem."""
    return open(path).read()

# 启用工具发现 — 注册 "discover_tools" 为可调用工具
registry.enable_tool_discovery()

# LLM 在 get_schemas() 中可以看到 discover_tools 并调用它来发现工具
schemas = registry.get_schemas(include_deferred=False)
```

也可以在构造时启用：

```python
registry = ToolRegistry(tool_discovery=True)
```

### 独立使用

如果你更想直接使用 `ToolDiscoveryTool` 而不将其注册到 registry 中：

```python
from toolregistry import ToolRegistry
from toolregistry.tool_discovery import ToolDiscoveryTool

registry = ToolRegistry()
# ... 注册工具 ...

discoverer = ToolDiscoveryTool(registry)

# 精确匹配 — 返回完整 schema
results = discoverer.discover("read_file")
print(results[0]["schema"])  # 完整工具定义

# 模糊搜索 — BM25 排序
results = discoverer.discover("read text file")
print(results[0]["name"])   # "read_file"
print(results[0]["score"])  # 1.23 (BM25 分数)
```

## 发现结果

每个结果是一个包含以下键的字典：

| 键 | 类型 | 说明 |
|----|------|------|
| `name` | `str` | 工具名称（标识符） |
| `description` | `str` | 工具描述 |
| `score` | `float` | BM25 相关性分数（精确匹配为 1.0） |
| `namespace` | `str \| None` | 工具命名空间（如有） |
| `deferred` | `bool` | 工具是否标记为延迟加载 |
| `schema` | `dict` | 完整工具 schema（精确匹配时总是包含；模糊搜索中仅延迟工具包含） |

**精确匹配**时，无论是否为延迟工具，结果始终包含完整 schema。**模糊搜索**时，仅延迟工具包含 schema，使 LLM 发现后可以立即调用。

```python
results = discoverer.discover("email", top_k=3)
for r in results:
    print(f"{r['name']}: {r['score']:.2f} — {r['description']}")
    if r.get("schema"):
        print(f"  Schema: {r['schema']}")
```

## 渐进式披露

大型 registry 的推荐工作流：

1. **将不常用的工具标记为延迟** — `ToolMetadata(defer=True)`
2. **使用 `get_schemas(include_deferred=False)`** 仅向 LLM 发送核心工具
3. **通过 `get_deferred_summaries()` 注入延迟工具摘要** 到 system prompt
4. **启用 `discover_tools`** 让 LLM 可以按名称或查询查找任何工具

```python
from toolregistry import Tool, ToolMetadata, ToolTag

registry = ToolRegistry(tool_discovery=True)

# 核心工具 — 始终可见
@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b

# 延迟工具 — 按需发现
registry.register(
    Tool.from_function(
        compress_file,
        metadata=ToolMetadata(
            defer=True,
            tags={ToolTag.FILE_SYSTEM},
        ),
    )
)

# 1. 非延迟工具的 schema 用于 LLM tools 参数
schemas = registry.get_schemas(include_deferred=False)

# 2. 延迟工具摘要用于 system prompt
summaries = registry.get_deferred_summaries()
# [{"name": "compress_file", "description": "Compress a file into a zip archive.", "namespace": None}]
```

### 延迟工具摘要

`get_deferred_summaries()` 返回延迟工具名称及首句描述的轻量列表，适合注入到 system prompt 中：

```python
summaries = registry.get_deferred_summaries()
for s in summaries:
    print(f"- {s['name']}: {s['description']}")
```

每个摘要包含：

| 键 | 类型 | 说明 |
|----|------|------|
| `name` | `str` | 工具名称 |
| `description` | `str` | 工具描述的第一句话 |
| `namespace` | `str \| None` | 工具命名空间（如有） |

仅包含**已启用**的延迟工具。描述会截断到第一句话（第一行中首个 `. ` 之前的文本）。

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
# 通过 enable_tool_discovery()
registry.enable_tool_discovery(field_weights={
    "name": 5.0,          # 提高精确名称匹配权重
    "description": 1.0,
    "tags": 3.0,          # 提高基于标签的发现权重
    "params": 0.5,
    "search_hint": 2.0,
})

# 或通过独立的 ToolDiscoveryTool
discoverer = ToolDiscoveryTool(
    registry,
    field_weights={
        "name": 5.0,
        "description": 1.0,
        "tags": 3.0,
        "params": 0.5,
        "search_hint": 2.0,
    },
)
```

## 重建索引

通过 `enable_tool_discovery()` 启用工具发现时，索引会在工具注册或注销时**自动重建**，由 ChangeCallback 机制驱动，无需手动干预。

对于独立使用 `ToolDiscoveryTool` 的场景，索引在构造时一次性构建。修改注册表后，需手动调用 `rebuild_index()`：

```python
@registry.register
def new_tool(x: int) -> int:
    """A newly added tool."""
    return x * 2

discoverer.rebuild_index()

results = discoverer.discover("newly added")
assert results[0]["name"] == "new_tool"
```

## 实现细节

ToolDiscoveryTool 使用 [zerodep](https://pypi.org/project/zerodep/) 的 `SparseIndex`（v0.2.2）的内置副本——一个纯 Python BM25/BM25F 实现，**零外部依赖**。索引完全存储在内存中，大小通常可忽略不计（100 个工具 ≈ 几 KB）。

BM25F 参数：

- `k1 = 1.5` — 词频饱和度
- `b = 0.75` — 文档长度归一化
- `delta = 1.0` — BM25+ 下限修正
