# LangChain 工具使用指南

???+ note "变更日志"
    新增于版本：0.4.9

LangChain 提供了各种预构建的工具包装器，但这些工具与其框架紧密耦合。这对于偏好使用 OpenAI 客户端或其他原生支持函数调用的框架的用户来说并不方便。为此，我们提供了一个 LangChain 工具的集成模块。

LangChain 集成模块使 ToolRegistry 能够支持基于 LangChain 的工具。通过该模块，你可以轻松注册和调用工具，同时受益于同步和异步两种调用模式，确保在不同环境中实现统一高效的执行。

## 使用指南

无需安装额外依赖。该集成是结构化的：任何暴露 `name`、`description`、参数模式以及同步和/或异步执行方法的对象，都可以通过 `source="langchain"` 注册。来自任意供应商或伙伴包的 `langchain_core.tools.BaseTool` 天然满足这些条件。

???+ warning "`langchain-community` 已停止维护"
    上游 `langchain-community` 已只读，最后一个版本是 2026 年 5 月的 0.4.2。ToolRegistry 不再依赖它。如果仍需要社区工具，请自行安装 `langchain-community`，或把底层可调用对象当作普通 Python 函数用 `registry.register(...)` 注册。

参数模式按以下顺序提取：`input_schema`、`args_schema`、`parameters` JSON Schema 字典、`args` 字典。执行方法按 `_run` / `run` / `func`（同步）与 `_arun` / `arun` / `coroutine`（异步）查找；仅同步的工具会通过工作线程提供异步调用。

1. **设置工具实例**

    使用任意 `BaseTool` 实现（例如 `langchain-openai` 等伙伴包，或自定义类），也可以使用具有相同结构的普通对象。无需社区工具包。

2. **注册工具**

    使用 `register()` 配合 `source="langchain"`，或 `register_async()` 配合 `source="langchain"` 注册工具。下面是一个自定义工具的示例：

    ```python
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel, Field
    from toolregistry import ToolRegistry

    class SearchInput(BaseModel):
        query: str = Field(description="Search query")

    class SearchTool(BaseTool):
        name: str = "search"
        description: str = "Search a local index"
        args_schema: type[BaseModel] = SearchInput

        def _run(self, query: str) -> str:
            return f"results for {query}"

    registry = ToolRegistry()
    registry.register(SearchTool(), source="langchain")
    ```

    普通对象同样可用——无需安装 LangChain：

    ```python
    class LocalSearch:
        name = "search"
        description = "Search a local index"
        args = {"query": {"type": "string", "description": "Search query"}}

        def _run(self, query: str) -> str:
            return f"results for {query}"

    registry.register(LocalSearch(), source="langchain")
    ```

    当然，也可以传入单个工具实例或工具列表。

3. **调用工具**

    注册完成后，你可以获取工具列表、获取工具 JSON 模式，或直接发起调用。这些操作与前面章节（MCP、OpenAPI、Hub 工具）中描述的操作没有区别。

## 示例

以下示例取自 `examples/langchain_related/openai_langchain_arxiv_example.py`，展示了如何将 OpenAI 客户端与 LangChain 工具结合使用：

```python
import os
from dotenv import load_dotenv
from openai import OpenAI
from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()

model_name = os.getenv("MODEL", "deepseek-v3")
API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

registry = ToolRegistry()

# Set up OpenAI client
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

def handle_tool_calls(response, messages):
    """Process tool calls in a loop until no more tool calls are needed"""
    while response.choices[0].message.tool_calls:
        tool_calls = response.choices[0].message.tool_calls
        print("Tool calls:", tool_calls)

        # Execute tool calls
        tool_responses = registry.execute_tool_calls(tool_calls)

        # Construct assistant messages with results
        assistant_tool_messages = registry.build_tool_call_messages(
            tool_calls, tool_responses
        )
        messages.extend(assistant_tool_messages)

        # Send results back to the model for continued conversation
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=registry.get_schemas(),
            tool_choice="auto",
        )
    return response

if __name__ == "__main__":
    # 任何 langchain_core BaseTool 均可；无需 langchain-community。
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel, Field

    class ArxivSearchInput(BaseModel):
        query: str = Field(description="Search query")

    class ArxivSearchTool(BaseTool):
        name: str = "arxiv_search"
        description: str = "Search arXiv for papers"
        args_schema: type[BaseModel] = ArxivSearchInput

        def _run(self, query: str) -> str:
            return f"arXiv results for {query!r} (demo tool)"

    registry.register(ArxivSearchTool(), source="langchain")
    print(registry.get_available_tools())

    user_input = input("Please enter your research interests: ")
    messages = [
        {
            "role": "user",
            "content": f"I'm interested in {user_input}. Please find related papers on arXiv for me.",
        }
    ]

    # Initiate chat completion request
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        tools=registry.get_schemas(),
        tool_choice="auto",
    )
    print(response)

    # Process tool calls in a loop
    response = handle_tool_calls(response, messages)

    # Output final response content
    if response.choices[0].message.content:
        print(response.choices[0].message.content)
```

## 注意事项

- 该集成无需额外依赖。只有在使用 `BaseTool` 类构建工具时才需要安装 `langchain-core`（或对应伙伴包）；带有 `name`、`description`、`args` 和 `_run` 的普通对象可直接使用。
- `langchain-community` 上游已停止维护，不再是 ToolRegistry 的依赖。
- `namespace` 参数允许在注册工具时灵活配置命名空间，以避免来自不同来源的命名冲突。

LangChain 集成模块增强了 ToolRegistry 对各种工具来源的支持灵活性，使开发者能够通过统一的接口更轻松地调用不同类型的工具。
