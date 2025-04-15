# ToolRegistry

[英文版](README_en.md)

一个用于以结构化方式管理和执行工具的 Python 库。

## 特性

- 工具注册与管理
- 为工具参数生成 JSON Schema
- 工具执行与结果处理
- 同步与异步工具支持
- 支持 [MCP sse](https://toolregistry.lab.oaklight.cn/mcp.html) 和 [OpenAPI](https://toolregistry.lab.oaklight.cn/openapi.html) 工具

## 完整文档

完整的文档请参阅 [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## 安装

### 基础安装

安装核心包（要求 **Python >= 3.8**）:

```bash
pip install toolregistry
```

### 附加支持模块安装

可以通过在方括号中指定附加模块来安装额外支持。例如，要安装特定的附加支持模块:

```bash
pip install toolregistry[mcp,openapi]
```

下表总结了可用的附加模块:

| 附加模块 | Python 要求    | 示例命令                          |
| -------- | -------------- | --------------------------------- |
| mcp      | Python >= 3.10 | pip install toolregistry[mcp]     |
| openapi  | Python >= 3.8  | pip install toolregistry[openapi] |

## 示例

### OpenAI 实现

[openai_tool_usage_example.py](examples/openai_tool_usage_example.py) 展示了如何将 ToolRegistry 与 OpenAI 的 API 集成。

### Cicada 实现

[cicada_tool_usage_example.py](examples/cicada_tool_usage_example.py) 演示了如何使用 ToolRegistry 与 Cicada 多模态模型结合使用。

## 基本工具调用

以下部分演示了如何调用基本工具。示例代码如下：

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

## MCP 集成

ToolRegistry 提供了对 MCP（模型上下文协议）工具的一流支持：

## 静态方法集成与工具中心

ToolRegistry 支持通过 `StaticMethodIntegration` 模块注册 Python 类的静态方法作为工具。这使开发者能够通过创建具有可重用静态方法的自定义工具类来扩展 ToolRegistry。

示例：

```python
from toolregistry import ToolRegistry

class CustomTools:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hello, {name}!"

registry = ToolRegistry()
registry.register_static_tools(CustomTools)

# 列出已注册工具
print(registry.get_available_tools())
# 输出: ['greet']
```

### 工具中心

[最新可用工具](src/toolregistry/hub/)

工具中心通过类中的静态方法封装常用功能，以增强功能性和组织性。

工具中心的可用工具示例包括：

- **Calculator**: 基本算术、科学运算、统计函数、财务计算等。
- **FileOps**: 文件操作，例如生成差异、打补丁和验证。
- **Filesystem**: 综合文件系统操作，例如目录列表、文件读写和路径操作。
- **UnitConverter**: 广泛的单位转换工具，包括温度、长度、重量等。

注册工具中心工具：

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_static_tools(Calculator, with_namespace=True)

# 获取可用工具列表
print(registry.get_available_tools())
# 输出: ['Calculator.add', 'Calculator.subtract', ..., 'Calculator.multiply', ...]
```

```python
registry.register_mcp_tools("http://localhost:8000/mcp/sse")

# 获取包含 MCP 工具的所有工具 JSON 数据
tools_json = registry.get_tools_json()
```

## OpenAPI 集成

ToolRegistry 支持通过标准化 API 接口与工具交互，支持 OpenAPI 集成：

```python
registry.register_openapi_tools("http://localhost:8000/") # 提供 baseurl 进行注册
registry.register_openapi_tools("./openapi_spec.json", "http://localhost/") # 通过本地 OpenAPI 规范文件和 base url 进行注册

# 获取包含 OpenAPI 工具的所有工具 JSON 数据
tools_json = registry.get_tools_json()
```

## 文档

完整的文档请参阅 [https://toolregistry.lab.oaklight.cn](https://toolregistry.lab.oaklight.cn)

## 许可证

该项目遵循 MIT 许可证，详细信息请参阅 [LICENSE](LICENSE) 文件。
