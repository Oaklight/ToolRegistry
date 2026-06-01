---
title: Home
author: Oaklight
hide:
  - navigation
  - title
---

<div class="tr-hero" markdown>

<p class="tr-kicker">Protocol-agnostic tools for LLM apps</p>

# Unified management for heterogeneous tools.

<p class="tr-hero__desc">ToolRegistry unifies tool registration, disclosure, execution, and result handling across native Python, MCP, OpenAPI, and future tool sources — with schema adapters for OpenAI-, Anthropic-, and Gemini-compatible APIs.</p>

<p class="tr-badges">
  <a href="https://pypi.org/project/toolregistry/"><img alt="PyPI version" src="https://img.shields.io/pypi/v/toolregistry?labelColor=475569&color=075985"></a>
  <a href="https://github.com/Oaklight/ToolRegistry/actions/workflows/ci.yml"><img alt="CI" src="https://img.shields.io/github/actions/workflow/status/Oaklight/ToolRegistry/ci.yml?branch=master&label=CI&labelColor=475569&color=0c4a6e"></a>
  <a href="https://opensource.org/licenses/MIT"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-0c4a6e?labelColor=475569"></a>
  <a href="https://arxiv.org/abs/2507.10593"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2507.10593-64748b?labelColor=475569"></a>
</p>

<p class="tr-actions">
  <a class="tr-button tr-button--primary" href="usage/basics/">Quick Start</a>
  <a class="tr-button tr-button--secondary" href="usage/function_calling/">Function Calling</a>
  <a class="tr-button tr-button--secondary" href="ecosystem/">Explore Ecosystem</a>
</p>

</div>

## Pick your path

<div class="tr-grid" markdown>

<div class="tr-card" markdown>
### Build with Python
Register normal Python callables and execute them with validation, logging, permissions, and concurrency controls.

[Start here →](usage/basics.md)
</div>

<div class="tr-card" markdown>
### Connect LLM providers
Generate schemas and recover tool calls across OpenAI, Anthropic, Gemini, and OpenAI-compatible APIs.

[Function calling →](usage/function_calling.md)
</div>

<div class="tr-card" markdown>
### Bring external tools
Import tools from MCP servers, OpenAPI specs, native Python classes, and future source adapters.

[Integrations →](usage/integrations/mcp.md)
</div>

<div class="tr-card" markdown>
### Serve a registry
Expose the same registry as OpenAPI or MCP with `toolregistry-server`, or use curated tools from `toolregistry-hub`.

[Architecture →](architecture/overview.md)
</div>

</div>

## Install

```bash
pip install toolregistry
```

Need MCP/OpenAPI integrations?

```bash
pip install "toolregistry[mcp,openapi]"
```

## Ecosystem

| Package | Use it when you need |
|---------|----------------------|
| **toolregistry** | Core registration, schema generation, execution, permissions, and metadata |
| [toolregistry-server](https://toolregistry-server.readthedocs.io/) | Serve registries as OpenAPI or MCP services |
| [toolregistry-hub](https://toolregistry-hub.readthedocs.io/) | Ready-to-use tools for search, fetch, datetime, unit conversion, and more |

## Cite

```bibtex
@article{ding2025toolregistry,
  title={Toolregistry: A protocol-agnostic tool management library for function-calling llms},
  author={Ding, Peng and Stevens, Rick},
  journal={arXiv preprint arXiv:2507.10593},
  year={2025}
}
```
