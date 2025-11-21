---
title: Home
author: Oaklight
hide:
  - navigation
---

# ToolRegistry: A Protocol-Agnostic Tool Management Library for OpenAI-Compatible LLM Applications

Welcome to the official documentation for **ToolRegistry**, a Python library designed to register, manage, and execute tools (functions) for Agentic AI and large language model applications. This documentation is organized by topic to help you quickly find and learn about different aspects of the library.

## Overview

ToolRegistry is a powerful Python library that simplifies the registration, management, and execution of tools (functions). Whether you're building systems integrated with large language models or need structured tool management, ToolRegistry provides a consistent interface supporting both synchronous and asynchronous tool calls.

This documentation details how to install, configure, and use the library in real projects. Browse the sections in the left menu to find the information you need.

## Getting Started

[![PyPI version](https://badge.fury.io/py/toolregistry.svg)](https://badge.fury.io/py/toolregistry)

Quickly start using ToolRegistry by installing it with this command:

```bash
pip install toolregistry
```

[Detailed setup instructions →](usage/installation.md)

## Documentation Contents

Here are brief introductions and links to each section:

- [**Installation Guide**](usage/installation.md)
  Detailed instructions for installing ToolRegistry, including basic installation and MCP-supported installation.

- [**Basic Usage Guide**](usage/basics.md)
  Provides getting started examples and tutorials to help you quickly learn tool registration, invocation, and management.

- [**Function calling via OpenAI Compatible API**](usage/function_calling.md)
  Explains how to use ToolRegistry with OpenAI compatible API through function calling.

- Register Tools from Various Sources

  - [**MCP Tool Integration**](usage/integrations/mcp.md)

  - [**OpenAPI Tool Integration**](usage/integrations/openapi.md)

  - [**Class-based Tools Collection**](usage/integrations/class.md)
  
  - [**Hub Tools Collection**](https://toolregistry-hub.readthedocs.io/)

  - [**LangChain Tool Integration**](usage/integrations/langchain.md)

- [**Concurrency Modes**](usage/concurrency_modes.md)
  Explains thread and process execution modes and their performance characteristics.

- [**Best Practices on Tool Implementation**](usage/best_practices.md)
  Offers principles and recommendations for designing and implementing tools.

- [**Examples**](examples/index.md)
  Demonstrates practical use cases, including consecutive tool call examples.

- [**API References**](api/index.md)
  Comprehensive API documentation for all classes and methods in ToolRegistry.

???+ note "API changes"
    Since version 0.4.12, the previously deprecated methods `ToolRegistry.register_static_tools`, `ToolRegistry.register_mcp_tools`, and `ToolRegistry.register_openapi_tools` have been **REMOVED**.

    Users must update their implementations to use the new methods: `ToolRegistry.register_from_class`, `ToolRegistry.register_from_mcp`, and `ToolRegistry.register_from_openapi`.
    
    Please ensure your codebase is compatible with this update for uninterrupted functionality.

## Citation

If you use ToolRegistry in your research or project, please consider cite it as:

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

ToolRegistry is licensed under the **MIT License**.