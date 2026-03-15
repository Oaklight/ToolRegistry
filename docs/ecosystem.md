---
title: 生态系统
---

# ToolRegistry 生态系统

ToolRegistry 生态系统由三个互补的包组成，它们协同工作，为 LLM 应用提供完整的工具管理解决方案。

## 概览

| 包名 | 描述 | PyPI | 文档 |
|------|------|------|------|
| **toolregistry** | 协议无关的工具管理核心库 | [![PyPI](https://img.shields.io/pypi/v/toolregistry)](https://pypi.org/project/toolregistry/) | [文档](https://toolregistry.readthedocs.io/zh/) |
| **toolregistry-server** | 用于暴露工具的服务器适配器（OpenAPI 和 MCP） | [![PyPI](https://img.shields.io/pypi/v/toolregistry-server)](https://pypi.org/project/toolregistry-server/) | [文档](https://toolregistry-server.readthedocs.io/zh/) |
| **toolregistry-hub** | 精选的即用型实用工具集合 | [![PyPI](https://img.shields.io/pypi/v/toolregistry-hub)](https://pypi.org/project/toolregistry-hub/) | [文档](https://toolregistry-hub.readthedocs.io/zh/) |

## 依赖关系图

```text
toolregistry          ← 核心：工具注册、模式生成、执行
    ↑
toolregistry-server   ← 服务器：OpenAPI 和 MCP 协议适配器
    ↑
toolregistry-hub      ← Hub：即用型工具实现
```

## 包详情

### toolregistry（核心）

生态系统的基础。提供：

- 协议无关的工具注册和管理
- 兼容 OpenAI 的函数调用模式生成
- 多模式并发工具执行
- MCP、OpenAPI、LangChain 和基于类的工具集成适配器

### toolregistry-server（服务器）

基于 `toolregistry` 构建。提供：

- OpenAPI REST 适配器，将工具暴露为 HTTP 端点
- MCP（模型上下文协议）适配器，用于 AI 原生工具服务
- 路由表，用于组织和管理工具端点
- 认证和配置支持
- CLI 快速服务器部署

### toolregistry-hub（Hub）

精选的实用工具集合，可通过 `toolregistry-server` 部署。提供：

- 计算器、单位转换、日期时间工具
- 文件操作和文件系统工具
- 多引擎网络搜索（Brave、Tavily、SearXNG 等）
- 网页内容获取、思考工具、待办事项
- Docker 镜像一键部署

---

!!! info "当前项目"

    您正在查看 **toolregistry** 的文档——为 OpenAI 兼容 LLM 应用提供协议无关工具管理的核心库。它是整个生态系统的基础。
