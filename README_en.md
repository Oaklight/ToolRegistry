# ToolRegistry

[![PyPI version](https://img.shields.io/pypi/v/toolregistry?color=green)](https://pypi.org/project/toolregistry/)
[![GitHub release](https://img.shields.io/github/v/release/Oaklight/ToolRegistry?color=green)](https://github.com/Oaklight/ToolRegistry/releases/latest)
[![CI](https://github.com/Oaklight/ToolRegistry/actions/workflows/ci.yml/badge.svg)](https://github.com/Oaklight/ToolRegistry/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Oaklight/toolregistry)

English Version | [中文版](README_zh.md)

A protocol-agnostic tool management library for function-calling LLMs.

**[Documentation](https://toolregistry.readthedocs.io)** · **[arXiv Paper](https://arxiv.org/abs/2507.10593)**

## Ecosystem

| Package | Description | PyPI | Docs |
|---------|-------------|------|------|
| [**toolregistry**](https://github.com/Oaklight/ToolRegistry) | Core library — tool registration, schema generation, execution | [![PyPI](https://img.shields.io/pypi/v/toolregistry?color=green)](https://pypi.org/project/toolregistry/) | [Docs](https://toolregistry.readthedocs.io/) |
| [**toolregistry-server**](https://github.com/Oaklight/toolregistry-server) | Server adapters — expose tools via OpenAPI & MCP | [![PyPI](https://img.shields.io/pypi/v/toolregistry-server?color=green)](https://pypi.org/project/toolregistry-server/) | [Docs](https://toolregistry-server.readthedocs.io/) |
| [**toolregistry-hub**](https://github.com/Oaklight/toolregistry-hub) | Ready-to-use tools — calculator, web search, file ops, etc. | [![PyPI](https://img.shields.io/pypi/v/toolregistry-hub?color=green)](https://pypi.org/project/toolregistry-hub/) | [Docs](https://toolregistry-hub.readthedocs.io/) |

```
toolregistry (core)
       ↓
toolregistry-server (tool server)
       ↓
toolregistry-hub (tool collection + server config)
```

## Features

- **Protocol-agnostic** — register tools from native Python functions/classes, MCP servers, OpenAPI specs, or LangChain tools through a unified interface
- **Multi-provider schemas** — generate tool schemas for OpenAI, Anthropic, and Gemini via [llm-rosetta](https://github.com/Oaklight/llm-rosetta)
- **Concurrent execution** — thread and process pool backends with per-tool timeout and concurrency control
- **Permission system** — tag-based policies (`READ_ONLY`, `DESTRUCTIVE`, `NETWORK`, etc.) with allow/deny/ask rules
- **Tool metadata & tags** — classify tools with `ToolTag`, `ToolMetadata`, namespace support, and source tracking
- **Admin panel** — built-in Web UI for monitoring tools, permissions, and runtime config (i18n: EN/ZH)
- **Think-augmented calling** — inject chain-of-thought reasoning into tool calls ([arXiv:2601.18282](https://arxiv.org/abs/2601.18282))
- **Declarative config** — load tool sources from JSONC/YAML config files
- **Zero-dependency core** — HTTP client, YAML parser, JSON Schema resolver all vendored; only `pydantic` and `llm-rosetta` as runtime deps

## Quick Start

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b

# Use with any LLM provider
schemas = registry.get_schemas(api_format="openai-chat")  # or "anthropic", "gemini"
result = registry["add"](1, 2)  # 3.0
```

See the [Usage Guide](https://toolregistry.readthedocs.io/en/stable/usage/basics.html) for MCP, OpenAPI, LangChain integrations and more.

## Installation

Requires **Python >= 3.10**.

```bash
pip install toolregistry                   # core
pip install toolregistry[mcp]              # + MCP support
pip install toolregistry[langchain]        # + LangChain support
pip install toolregistry-hub               # ready-to-use tools (separate package)
```

## Citation

```bibtex
@software{toolregistry2025,
  title={ToolRegistry: A Protocol-Agnostic Tool Management Library for OpenAI-Compatible LLM Applications},
  author={Peng Ding},
  year={2025},
  url={https://github.com/Oaklight/ToolRegistry},
  note={A Python library for unified tool registration, execution, and management across multiple protocols in OpenAI-compatible LLM applications}
}

@article{ding2025toolregistry,
  title={ToolRegistry: A Protocol-Agnostic Tool Management Library for Function-Calling LLMs},
  author={Ding, Peng},
  journal={arXiv preprint arXiv:2507.10593},
  year={2025}
}
```

## License

MIT — see [LICENSE](LICENSE) for details.
