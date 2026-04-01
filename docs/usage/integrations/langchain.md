# LangChain 工具使用指南

???+ note "变更日志"
    新增于版本：0.4.9

LangChain 提供了各种预构建的工具包装器，但这些工具与其框架紧密耦合。这对于偏好使用 OpenAI 客户端或其他原生支持函数调用的框架的用户来说并不方便。为此，我们提供了一个 LangChain 工具的集成模块。

LangChain 集成模块使 ToolRegistry 能够支持基于 LangChain 的工具。通过该模块，你可以轻松注册和调用工具，同时受益于同步和异步两种调用模式，确保在不同环境中实现统一高效的执行。

## 使用指南

要集成 LangChain，请确保已安装 [langchain] 依赖扩展（`pip install toolregistry[langchain]`）。按照以下步骤注册和使用工具：

1. **设置 LangChain 工具实例**

    任何兼容 `langchain_core.tools.BaseTool` 类型的工具都可以直接注册。

    可以使用第三方库（例如 [langchain_community.tools](https://github.com/langchain-ai/langchain) 中的工具）来创建工具实例，也可以利用你现有的代码来构建 LangChain 工具。

2. **注册工具**

    使用注册器的 `register_from_langchain` 或 `register_from_langchain_async` 接口将 LangChain 工具注册到注册器中。以下是注册两个工具（`ArxivQueryRun` 和 `PubmedQueryRun`）的列表示例。

    ```python
    from langchain_community.tools import ArxivQueryRun, PubmedQueryRun
    from toolregistry import ToolRegistry

    registry = ToolRegistry()

    registry.register_from_langchain([ArxivQueryRun(), PubmedQueryRun()])
    ```

    当然，你也可以传入单个工具实例。

    ```python
    registry.register_from_langchain(ArxivQueryRun())
    ```

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
    from langchain_community.tools import ArxivQueryRun, PubmedQueryRun

    # Register LangChain tools
    arxiv_tool = ArxivQueryRun()
    pubmed_tool = PubmedQueryRun()
    registry.register_from_langchain([arxiv_tool, pubmed_tool])
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

- 请确保已安装相应的扩展依赖（例如 langchain）。
- `with_namespace` 参数允许在注册工具时灵活配置命名空间，以避免来自不同来源的命名冲突。

LangChain 集成模块增强了 ToolRegistry 对各种工具来源的支持灵活性，使开发者能够通过统一的接口更轻松地调用不同类型的工具。
