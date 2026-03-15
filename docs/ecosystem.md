---
title: Ecosystem
---

# ToolRegistry Ecosystem

The ToolRegistry ecosystem consists of three complementary packages that work together to provide a complete tool management solution for LLM applications.

## Overview

| Package | Description | PyPI | Docs |
|---------|-------------|------|------|
| **toolregistry** | Core library for protocol-agnostic tool management | [![PyPI](https://img.shields.io/pypi/v/toolregistry)](https://pypi.org/project/toolregistry/) | [Docs](https://toolregistry.readthedocs.io/) |
| **toolregistry-server** | Server adapters (OpenAPI & MCP) for exposing tools | [![PyPI](https://img.shields.io/pypi/v/toolregistry-server)](https://pypi.org/project/toolregistry-server/) | [Docs](https://toolregistry-server.readthedocs.io/) |
| **toolregistry-hub** | Curated collection of ready-to-use utility tools | [![PyPI](https://img.shields.io/pypi/v/toolregistry-hub)](https://pypi.org/project/toolregistry-hub/) | [Docs](https://toolregistry-hub.readthedocs.io/) |

## Dependency Diagram

```text
toolregistry          ← Core: tool registration, schema generation, execution
    ↑
toolregistry-server   ← Server: OpenAPI & MCP protocol adapters
    ↑
toolregistry-hub      ← Hub: ready-to-use tool implementations
```

## Package Details

### toolregistry (Core)

The foundation of the ecosystem. Provides:

- Protocol-agnostic tool registration and management
- OpenAI-compatible function calling schema generation
- Concurrent tool execution with multiple modes
- Integration adapters for MCP, OpenAPI, LangChain, and class-based tools

### toolregistry-server (Server)

Built on top of `toolregistry`. Provides:

- OpenAPI REST adapter for exposing tools as HTTP endpoints
- MCP (Model Context Protocol) adapter for AI-native tool serving
- Route table for organizing and managing tool endpoints
- Authentication and configuration support
- CLI for quick server deployment

### toolregistry-hub (Hub)

A curated set of utility tools, deployable via `toolregistry-server`. Provides:

- Calculator, unit converter, date/time tools
- File operations and file system tools
- Multi-engine web search (Brave, Tavily, SearXNG, etc.)
- Web content fetching, think tool, todo list
- Docker image for one-command deployment

---

!!! info "This Project"

    You are currently viewing the documentation for **toolregistry** — the core library that provides protocol-agnostic tool management for OpenAI-compatible LLM applications. It serves as the foundation upon which the rest of the ecosystem is built.
