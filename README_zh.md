# ToolRegistry

[English Version](README_en.md) | [中文版](README_zh.md)

一个用于以结构化方式管理和执行工具的 Python 库。

## 特性

- 工具注册与管理
- 工具参数的 JSON Schema 生成
- 工具执行与结果处理
- 支持同步和异步工具
- 支持 Python 原生函数和类方法作为工具
- 支持多种 [MCP](https://toolregistry.lab.oaklight.cn/mcp.html) 传输方式: STDIO, streamable http, sse, websocket, FastMCP 实例等
- 支持 [OpenAPI](https://toolregistry.lab.oaklight.cn/openapi.html) 工具

## 完整文档

完整文档可访问 [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## API 弃用（自 0.4.12 起）

从版本 0.4.12 开始，之前已被弃用的方法 `ToolRegistry.register_static_tools`、`ToolRegistry.register_mcp_tools` 和 `ToolRegistry.register_openapi_tools` 已被**移除**。用户必须更新其实现，改为使用新方法：`ToolRegistry.register_from_class`、`ToolRegistry.register_from_mcp` 和 `ToolRegistry.register_from_openapi`。请确保您的代码库与此更新兼容，以确保功能不受影响。

## 安装

### 基本安装

安装核心包（需要 **Python >= 3.8**）：

```bash
pip install toolregistry
```

### 安装额外支持模块

通过在括号中指定额外模块来安装。例如，要安装特定的额外支持：

```bash
pip install toolregistry[mcp,openapi]
```

以下是可用额外模块的总结表：

| 额外模块  | Python 要求    | 示例命令                            |
| --------- | -------------- | ----------------------------------- |
| mcp       | Python >= 3.10 | pip install toolregistry[mcp]       |
| openapi   | Python >= 3.8  | pip install toolregistry[openapi]   |
| langchain | Python >= 3.9  | pip install toolregistry[langchain] |
| hub       | Python >= 3.8  | pip install toolregistry[hub]       |

### Hub 工具安装

**注意**：从最新版本开始，hub 工具已移至独立包 `toolregistry-hub`。您可以通过两种方式安装 hub 工具：

1. **独立安装**：

   ```bash
   pip install toolregistry-hub
   ```

2. **通过额外模块**：

   ```bash
   pip install toolregistry[hub]
   ```

两种方法提供相同的功能。独立安装允许您独立使用 hub 工具或与其他兼容库一起使用。

## 示例

### OpenAI 实现

[openai_tool_usage_example.py](examples/openai_tool_usage_example.py) 展示了如何将 ToolRegistry 与 OpenAI 的 API 集成。

### Cicada 实现

[cicada_tool_usage_example.py](examples/cicada_tool_usage_example.py) 演示了如何将 ToolRegistry 与 Cicada 多模态模型结合使用。

## 基本工具调用

本节展示了如何调用基本工具。示例：

```python
from toolregistry import ToolRegistry

registry = ToolRegistry()

@registry.register
def add(a: float, b: float) -> float:
    """将两个数字相加。"""
    return a + b

available_tools = registry.get_available_tools()

print(available_tools) # ['add']

add_func = registry.get_callable('add')
print(type(add_func)) # <class 'function'>
add_result = add_func(1, 2)
print(add_result) # 3

add_func = registry['add']
print(type(add_func)) # <class 'function'>
add_result = add_func(4, 5)
print(add_result) # 9
```

更多使用示例，请参考 [文档 - 使用](https://toolregistry.lab.oaklight.cn/usage.html)

## MCP 集成

ToolRegistry 提供对 MCP（模型上下文协议）工具的一流支持：

```python
# transport 可以是 URL 字符串、脚本路径、transport 实例或 MCP 实例。
transport = "https://mcphub.url/mcp"  # 使用 HTTP Streamable MCP
transport = "http://localhost:8000/sse/test_group"  # 使用 legacy HTTP+sse
transport = "examples/mcp_related/mcp_servers/math_server.py"  # 本地路径
transport = {
    "mcpServers": {
        "make_mcp": {
            "command": f"{Path.home()}/mambaforge/envs/toolregistry_dev/bin/python",
            "args": [
                f"{Path.home()}/projects/toolregistry/examples/mcp_related/mcp_servers/math_server.py"
            ],
            "env": {},
        }
    }
} # 示例 MCP 配置字典
transport = FastMCP(name="MyFastMCP")  # 使用 FastMCP 实例
transport = StreamableHttpTransport(url="https://mcphub.example.com/mcp", headers={"Authorization": "Bearer token"})  # 使用自定义头的 transport 实例

registry.register_from_mcp(transport)

# 获取所有工具的 JSON，包括 MCP 工具
tools_json = registry.get_tools_json()
```

## OpenAPI 集成（更新至 0.4.12）

`register_from_openapi`方法现在接受两个参数：

- `client_config`：一个`toolregistry.openapi.HttpxClientConfig`对象，用于配置与 API 交互的 HTTP 客户端。可以配置请求头、认证、超时等设置，提供比以前版本更大的灵活性。
- `openapi_spec`：以`Dict[str, Any]`形式表示的 OpenAPI 规范，使用`load_openapi_spec`或`load_openapi_spec_async`等函数加载。这些函数支持通过文件路径或 URL 获取 OpenAPI 规范，或者通过 API 的基础 URL 获取，并返回解析后的 OpenAPI 规范字典。

示例：

```python
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec

client_config = HttpxClientConfig(base_url="http://localhost:8000")
openapi_spec = load_openapi_spec("./openapi_spec.json")
openapi_spec = load_openapi_spec("http://localhost:8000")
openapi_spec = load_openapi_spec("http://localhost:8000/openapi.json")

registry.register_from_openapi(
    client_config=client_config,
    openapi_spec=openapi_spec
)

# 获取所有工具的JSON，包括OpenAPI工具
tools_json = registry.get_tools_json()
```

### 注意

在使用 `load_openapi_spec` 或 `load_openapi_spec_async` 函数时，具有以下行为：

1. **提供基础 URL**：如果仅指定基础 URL（例如 `http://localhost:8000`），加载器将尝试“尽力而为”自动发现 OpenAPI 规范文件。会检查诸如 `http://<base_url>/openapi.json` 或 `http://<base_url>/swagger.json` 的端点。如果自动发现失败，请确保基础 URL 是准确的并且规范文件可以访问。

2. **提供文件路径**：如果您提供文件路径（例如 `./openapi_spec.json`），函数将直接从文件中加载 OpenAPI 规范。与简单的直接加载不同，此功能还包括解析 OpenAPI 规范中常见的 `$ref` 块。这确保返回的字典中任何模式引用都被完全解析。

## LangChain 集成

LangChain 集成模块允许 ToolRegistry 无缝注册和调用 LangChain 工具，支持同步和异步调用。

```python
from langchain_community.tools import ArxivQueryRun, PubmedQueryRun
from toolregistry import ToolRegistry

registry = ToolRegistry()

registry.register_from_langchain([ArxivQueryRun(), PubmedQueryRun()])
tools_json = registry.get_tools_json()
```

## 注册 Class 工具

Class 工具通过 `register_from_class` 方法注册到 ToolRegistry。这允许开发人员通过创建具有可重用方法的自定义工具类来扩展 ToolRegistry 的功能。

示例：

```python
from toolregistry import ToolRegistry

class StaticExample:
    @staticmethod
    def greet(name: str) -> str:
        return f"你好，{name}！"

class InstanceExample:
    def __init__(self, name: str):
        self.name = name

    def greet(self, name: str) -> str:
        return f"你好，{name}！我是 {self.name}。"

registry = ToolRegistry()
registry.register_from_class(StaticExample, with_namespace=True)
print(registry.get_available_tools())  # ['static_example.greet']
print(registry["static_example.greet"]("Alice"))  # 你好，Alice！

registry = ToolRegistry()
registry.register_from_class(InstanceExample("Bob"), with_namespace=True)
print(registry.get_available_tools())  # ['instance_example.greet']
print(registry["instance_example.greet"]("Alice"))  # 你好，Alice！我是 Bob。
```

### Hub 工具

[最新可用工具](src/toolregistry/hub/)

Hub 工具将常用功能封装为类中的方法，以增强功能性和组织性。

可用的 Hub 工具示例包括：

- **Calculator**：基本算术、科学运算、统计函数、金融计算等。
- **FileOps**：文件操作如差异生成、补丁、验证、合并和拆分。
- **Filesystem**：全面的文件系统操作，如目录列表、文件读写、路径规范化和查询文件属性。
- **UnitConverter**：广泛的单位转换，如温度、长度、重量、体积等。
- **WebSearch**：网页搜索功能，支持多种引擎，如 Bing、Google 和 SearXNG 等。
- **Fetch**：从 URL 获取内容。

注册 Hub 工具：

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_from_class(Calculator, with_namespace=True)

# 获取可用工具列表
print(registry.get_available_tools())
# ['calculator-list_allowed_fns', 'calculator-help', 'calculator-evaluate']
```

### 社区贡献

我们欢迎社区贡献新的工具类到 ToolRegistry！如果您有其他常用工具类的设计或实现，欢迎通过 Pull Request 提交到 [GitHub 仓库](https://github.com/yourrepository/toolregistry)。您的贡献将帮助拓展工具的多样性和适用性。

## 引用

如果您在研究或项目中使用了 ToolRegistry，请引用：

```bibtex
@software{toolregistry2025,
  title={ToolRegistry: A Protocol-Agnostic Tool Management Library for OpenAI-Compatible LLM Applications},
  author={Peng Ding},
  year={2025},
  url={https://github.com/Oaklight/ToolRegistry},
  note={A Python library for unified tool registration, execution, and management across multiple protocols in OpenAI-compatible LLM applications}
}
```

## 许可证

此项目根据 MIT 许可证授权 - 详情请参阅 [LICENSE](LICENSE) 文件。
