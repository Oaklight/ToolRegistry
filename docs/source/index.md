# ToolRegistry Documentation

Welcome to the official documentation for **ToolRegistry**, a Python library designed to register, manage, and execute tools (functions) for Agentic AI and large language model applications. This documentation is organized by topic to help you quickly find and learn about different aspects of the library.

## Documentation Contents

Here are brief introductions and links to each section:

- [**Installation Guide**](installation)
  Detailed instructions for installing ToolRegistry, including basic installation and MCP-supported installation.

- [**Usage Guide**](usage)
  Provides getting started examples and tutorials to help you quickly learn tool registration, invocation, and management.

  - [**OpenAI Integration**](openai)
    Explains how to use ToolRegistry with OpenAI API through function calling.

  - [**MCP Tool Usage**](mcp)
    Guides on integrating MCP (Modular Component Protocol) with ToolRegistry to register and call MCP tools.

  - [**OpenAPI Integration**](openapi)
    Guides on integrating OpenAPI specifications with ToolRegistry to register and call OpenAPI tools.

  - [**Hub Tools Collection**](hub)
    Provides a collection of utility tools for common llm function calling usage. These tools simplify common tasks and enhance productivity in projects requiring structured tool management.

  - [**Concurrency Modes**](concurrency_modes)
    Explains thread and process execution modes and their performance characteristics.

  - [**Examples**](examples)
    Demonstrates practical use cases, including consecutive tool call examples.

  - [**Best Practices**](best_practices)
    Offers principles and recommendations for designing and implementing tools.

<!-- - **Dependencies**
  Lists auxiliary projects that provide additional functionality. -->

- [**API References**](api/toolregistry)
  Comprehensive API documentation for all classes and methods in ToolRegistry.

```{toctree}
:maxdepth: 1
:caption: Documentation
:hidden:

Getting Started <self>
installation
usage
API Reference <api/toolregistry>
```

## API Changes (starting 0.4.4)

Starting from version 0.4.4, several API methods have been updated for better consistency and usability:

- `ToolRegistry.register_static_tools` has been replaced by `ToolRegistry.register_from_class`.
- `ToolRegistry.register_mcp_tools` has been replaced by `ToolRegistry.register_from_mcp`.
- `ToolRegistry.register_openapi_tools` has been replaced by `ToolRegistry.register_from_openapi`.

The old methods are planned to be deprecated soon, so please migrate to the new interfaces as soon as possible. For backward compatibility, the old names remain as aliases to the new ones.

## Overview

ToolRegistry is a powerful Python library that simplifies the registration, management, and execution of tools (functions). Whether you're building systems integrated with large language models or need structured tool management, ToolRegistry provides a consistent interface supporting both synchronous and asynchronous tool calls.

This documentation details how to install, configure, and use the library in real projects. Browse the sections in the left menu to find the information you need.

## Getting Started

Quickly start using ToolRegistry by installing it with this command:

```bash
pip install toolregistry
```

[Detailed setup instructions →](./installation)

## License

ToolRegistry is licensed under the **MIT License**.
