# 安装

本指南提供了安装 ToolRegistry 不同功能集的详细说明。

## 基础安装

使用 pip 安装 ToolRegistry：

```bash
pip install toolregistry
```

这将安装基本工具注册和执行所需的核心功能。

## 安装可选依赖

ToolRegistry 支持各种需要额外依赖的集成。您可以使用以下命令安装这些依赖：

### MCP 支持

用于模型上下文协议 (MCP) 集成：

```bash
pip install toolregistry[mcp]
```

### OpenAPI 支持

用于 OpenAPI/Swagger 集成：

```bash
pip install toolregistry[openapi]
```

### LangChain 支持

用于 LangChain 工具集成：

```bash
pip install toolregistry[langchain]
```

### 所有功能

安装所有可选依赖：

```bash
pip install toolregistry[all]
```

## 开发安装

如果您想为 ToolRegistry 做贡献或需要最新的开发版本：

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install -e .[all]
```

## 验证

要验证您的安装，请运行：

```python
import toolregistry
print(toolregistry.__version__)
```

## 系统要求

- Python 3.8 或更高版本
- 操作系统：Windows、macOS 或 Linux

## 故障排除

### 常见问题

**导入错误**：如果遇到导入错误，请确保您已为要使用的功能安装了正确的可选依赖。

**版本冲突**：如果遇到依赖冲突，请考虑使用虚拟环境：

```bash
python -m venv toolregistry-env
source toolregistry-env/bin/activate  # Windows 上：toolregistry-env\Scripts\activate
pip install toolregistry[all]
```

### 获取帮助

如果在安装过程中遇到问题：

1. 查看 [GitHub Issues](https://github.com/Oaklight/ToolRegistry/issues)
2. 创建一个包含您的系统信息和错误详情的新问题
3. 加入我们的社区讨论