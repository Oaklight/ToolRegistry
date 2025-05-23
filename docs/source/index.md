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

[Detailed setup instructions →](usage/installation)

## Documentation Contents

Here are brief introductions and links to each section:

- [**Installation Guide**](usage/installation)
  Detailed instructions for installing ToolRegistry, including basic installation and MCP-supported installation.

- [**Basic Usage Guide**](usage/basics)
  Provides getting started examples and tutorials to help you quickly learn tool registration, invocation, and management.

- [**Function calling via OpenAI Compatible API**](usage/openai)
  Explains how to use ToolRegistry with OpenAI compatible API through function calling.

- Register Tools from Various Sources

  - [**MCP Tool Integration**](usage/integrations/mcp)

  - [**OpenAPI Tool Integration**](usage/integrations/openapi)

  - [**LangChain Tool Integration**](usage/integrations/langchain)

  - [**Hub Tools Collection**](usage/integrations/hub)

- [**Concurrency Modes**](usage/concurrency_modes)
  Explains thread and process execution modes and their performance characteristics.

- [**Best Practices on Tool Implementation**](usage/best_practices)
  Offers principles and recommendations for designing and implementing tools.

- [**Examples**](examples)
  Demonstrates practical use cases, including consecutive tool call examples.

- [**API References**](api/toolregistry)
  Comprehensive API documentation for all classes and methods in ToolRegistry.

```{note}
Starting from version 0.4.4, several API methods have been updated for better consistency and usability:

- `ToolRegistry.register_static_tools` has been replaced by `ToolRegistry.register_from_class`.
- `ToolRegistry.register_mcp_tools` has been replaced by `ToolRegistry.register_from_mcp`.
- `ToolRegistry.register_openapi_tools` has been replaced by `ToolRegistry.register_from_openapi`.

The old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, the old names remain as aliases to the new ones.
```

```{toctree}
:caption: Documentation
:hidden:

usage/index
examples/index
api/index
```

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
```

## License

ToolRegistry is licensed under the **MIT License**.
