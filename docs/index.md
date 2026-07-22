---
title: 首页
author: Oaklight
hide:
  - navigation
  - title
---

<div class="tr-hero" markdown>

<p class="tr-kicker">面向 LLM 应用的协议无关工具层</p>

# 异构工具的统一管理层。

<p class="tr-hero__desc">统一注册、描述、发现、执行并返回来自原生 Python、MCP、OpenAPI 以及未来更多来源的工具，并为 OpenAI、Anthropic 和 Gemini 兼容 API 适配工具 schema 与调用格式。</p>

<p class="tr-badges">
  <a href="https://pypi.org/project/toolregistry/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/toolregistry?labelColor=475569&color=075985"></a>
  <a href="https://github.com/Oaklight/ToolRegistry/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Oaklight/ToolRegistry/ci.yml?branch=master&label=CI&labelColor=475569&color=0c4a6e"></a>
  <a href="https://opensource.org/licenses/MIT"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-0c4a6e?labelColor=475569"></a>
  <a href="https://arxiv.org/abs/2507.10593"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2507.10593-64748b?labelColor=475569"></a>
</p>

<p class="tr-actions">
  <a class="tr-button tr-button--primary" href="usage/basics/">快速上手</a>
  <a class="tr-button tr-button--secondary" href="usage/function_calling/">函数调用</a>
  <a class="tr-button tr-button--secondary" href="ecosystem/">了解生态系统</a>
</p>

</div>

## 选择你的路径

<div class="grid cards" markdown>

-   :material-language-python:{ .lg .middle } **用 Python 构建**

    ---

    注册普通 Python callable，并使用验证、日志、权限和并发控制来执行工具。

    [:octicons-arrow-right-24: 从这里开始](usage/basics.md)

-   :material-robot:{ .lg .middle } **连接 LLM Provider**

    ---

    为 OpenAI、Anthropic、Gemini 和 OpenAI-compatible API 生成 schema 并恢复工具调用。

    [:octicons-arrow-right-24: 函数调用](usage/function_calling.md)

-   :material-puzzle:{ .lg .middle } **接入外部工具**

    ---

    从 MCP server、OpenAPI spec、原生 Python class 以及未来更多 source adapter 导入工具。

    [:octicons-arrow-right-24: 集成指南](usage/integrations/mcp.md)

-   :material-server-network:{ .lg .middle } **服务化注册表**

    ---

    用 `toolregistry-server` 将同一份 registry 暴露为 OpenAPI 或 MCP，或直接使用 `toolregistry-hub` 的现成工具。

    [:octicons-arrow-right-24: 架构概览](architecture/overview.md)

</div>

## 安装

```bash
pip install toolregistry
```

需要 MCP/OpenAPI 集成？

```bash
pip install "toolregistry[mcp,openapi]"
```

## 生态系统

| 包名 | 适用场景 |
|------|----------|
| **toolregistry** | 核心注册、schema 生成、执行、权限和元数据管理 |
| [toolregistry-server](https://toolregistry-server.readthedocs.io/) | 将 registry 服务化为 OpenAPI 或 MCP 服务 |
| [toolregistry-hub](https://toolregistry-hub.readthedocs.io/) | 搜索、网页抓取、日期时间、单位转换等现成工具 |

## 引用

```bibtex
@article{ding2025toolregistry,
  title={Toolregistry: A protocol-agnostic tool management library for function-calling llms},
  author={Ding, Peng and Stevens, Rick},
  journal={arXiv preprint arXiv:2507.10593},
  year={2025}
}
```
