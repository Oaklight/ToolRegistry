---
title: 首页
author: Oaklight
hide:
  - navigation
---

# ToolRegistry: 面向 OpenAI 兼容 LLM 应用的协议无关工具管理库

欢迎来到 **ToolRegistry** 的官方文档，这是一个专为智能体 AI 和大型语言模型应用设计的 Python 库，用于注册、管理和执行工具（函数）。本文档按主题组织，帮助您快速找到并学习库的不同方面。

## 概览

ToolRegistry 是一个强大的 Python 库，简化了工具（函数）的注册、管理和执行。无论您是在构建与大型语言模型集成的系统，还是需要结构化的工具管理，ToolRegistry 都提供了一致的接口，支持同步和异步工具调用。

本文档详细介绍了如何在实际项目中安装、配置和使用该库。浏览左侧菜单中的各个部分以找到您需要的信息。

## 快速开始

[![PyPI version](https://badge.fury.io/py/toolregistry.svg)](https://badge.fury.io/py/toolregistry)

通过以下命令快速开始使用 ToolRegistry：

```bash
pip install toolregistry
```

[详细安装说明 →](usage/installation.md)

## 文档内容

以下是各个部分的简要介绍和链接：

- [**安装指南**](usage/installation.md)
  详细的 ToolRegistry 安装说明，包括基础安装和支持 MCP 的安装。

- [**基础用法指南**](usage/basics.md)
  提供入门示例和教程，帮助您快速学习工具注册、调用和管理。

- [**通过 OpenAI 兼容 API 进行函数调用**](usage/function_calling.md)
  解释如何通过函数调用将 ToolRegistry 与 OpenAI 兼容 API 一起使用。

- 从各种来源注册工具

  - [**MCP 工具集成**](usage/integrations/mcp.md)

  - [**OpenAPI 工具集成**](usage/integrations/openapi.md)

  - [**基于类的工具集合**](usage/integrations/class.md)
  
  - [**Hub 工具集合**](https://toolregistry-hub.readthedocs.io/)

  - [**LangChain 工具集成**](usage/integrations/langchain.md)

- [**并发模式**](usage/concurrency_modes.md)
  解释线程和进程执行模式及其性能特征。

- [**工具实现最佳实践**](usage/best_practices.md)
  提供设计和实现工具的原则和建议。

- [**示例**](examples/index.md)
  演示实际用例，包括连续工具调用示例。

- [**API 参考**](api/index.md)
  ToolRegistry 中所有类和方法的全面 API 文档。

???+ note "API 变更"
    从版本 0.4.12 开始，之前已弃用的方法 `ToolRegistry.register_static_tools`、`ToolRegistry.register_mcp_tools` 和 `ToolRegistry.register_openapi_tools` 已被**移除**。

    用户必须更新其实现以使用新方法：`ToolRegistry.register_from_class`、`ToolRegistry.register_from_mcp` 和 `ToolRegistry.register_from_openapi`。
    
    请确保您的代码库与此更新兼容，以保证功能不中断。

## 引用

如果您在研究或项目中使用 ToolRegistry，请考虑引用它：

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

## 许可证

ToolRegistry 采用 **MIT 许可证**。