# ToolRegistry

[English Version](README_en.md)

一个用于以结构化方式管理和执行工具的 Python 库。

## 特性

- 工具注册与管理
- 工具参数的 JSON Schema 生成
- 工具执行与结果处理
- 支持同步和异步工具
- 支持 [MCP sse](https://toolregistry.lab.oaklight.cn/mcp.html)、[OpenAPI](https://toolregistry.lab.oaklight.cn/openapi.html) 工具

## 完整文档

完整文档可访问 [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## API 变更（从 0.4.4 开始）

之前用于从类中注册静态方法的 `ToolRegistry.register_static_tools` 方法已被替换为 `ToolRegistry.register_from_class`。类似地，`ToolRegistry.register_mcp_tools` 已被替换为 `ToolRegistry.register_from_mcp`，`ToolRegistry.register_openapi_tools` 已被替换为 `ToolRegistry.register_from_openapi`。所有旧方法计划很快被弃用，请尽快迁移到新的接口。为了向后兼容，旧名称仍作为新名称的别名。

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

| 额外模块 | Python 要求    | 示例命令                          |
| -------- | -------------- | --------------------------------- |
| mcp      | Python >= 3.10 | pip install toolregistry[mcp]     |
| openapi  | Python >= 3.8  | pip install toolregistry[openapi] |

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
registry.register_from_mcp"http://localhost:8000/sse")

# 获取所有工具的 JSON，包括 MCP 工具
tools_json = registry.get_tools_json()
```

## OpenAPI 集成

ToolRegistry 支持与 OpenAPI 集成，以使用标准化 API 接口与工具交互：

```python
registry.register_from_openapi("http://localhost:8000/") # 提供基础 URL
registry.register_from_openapi("./openapi_spec.json", "http://localhost/") # 提供本地 OpenAPI 规范文件和基础 URL

# 获取所有工具的 JSON，包括 OpenAPI 工具
tools_json = registry.get_tools_json()
```

## 注册 Hub 工具

Hub 工具通过 `register_from_class` 方法注册到 ToolRegistry。这允许开发人员通过创建具有可重用方法的自定义工具类来扩展 ToolRegistry 的功能。

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

- **Calculator**：基本算术、科学运算、统计函数、财务计算等。
- **FileOps**：文件操作，例如生成差异、打补丁和验证。
- **Filesystem**：全面的文件系统操作，例如目录列表、文件读写和路径操作。
- **UnitConverter**：广泛的单位转换工具，例如温度、长度、重量等。
- **WebSearch**：支持多种搜索引擎（包括SearxNG和Google）的网页搜索功能。

注册 Hub 工具：

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_from_class(Calculator, with_namespace=True)

# 获取可用工具列表
print(registry.get_available_tools())
# 输出：['Calculator.add', 'Calculator.subtract', ..., 'Calculator.multiply', ...]
```

## 许可证

此项目根据 MIT 许可证授权 - 详情请参阅 [LICENSE](LICENSE) 文件。
