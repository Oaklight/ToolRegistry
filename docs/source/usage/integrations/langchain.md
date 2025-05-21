# LangChain Tool Usage Guide

```{note}
New in version: 0.4.9
```

LangChain provides various pre-built tool wrappers, but these tools are tightly coupled with its framework. This makes them inconvenient for users who prefer to use the OpenAI client or other frameworks that natively support function calling. To address this, we provide an integration module for LangChain tools.

The LangChain integration module enables the ToolRegistry to support LangChain-based tools. With this module, you can easily register and invoke tools while benefiting from both synchronous and asynchronous calling modes, ensuring unified efficient execution across different environments.

## Usage Guide

To integrate LangChain, ensure you have installed the [langchain] dependency extension (`pip install toolregistry[langchain]`). LangChain support requires *Python version >= 3.9*. Follow these steps to register and use tools:

1. **Setup LangChain Tool Instances**

    Any tool compatible with the `langchain_core.tools.BaseTool` type can be registered directly.

    Use third-party libraries, such as tools from [langchain_community.tools](https://github.com/langchain-ai/langchain), to create tool instances. Alternatively, leverage your existing code for building LangChain tools.

2. **Register Tools**

    Use the registry's `register_from_langchain` or `register_from_langchain_async` interface to register LangChain tools into the registry. Here is an example of registering a list of two tools: `ArxivQueryRun` and `PubmedQueryRun`.

    ```python
    from langchain_community.tools import ArxivQueryRun, PubmedQueryRun
    from toolregistry import ToolRegistry

    registry = ToolRegistry()
    
    registry.register_from_langchain([ArxivQueryRun(), PubmedQueryRun()])
    ```

    You certainly can pass in a single tool instance if needed.

    ```python
    registry.register_from_langchain(ArxivQueryRun())
    ```

3. **Invoke Tools**

    After registration, you can retrieve tool lists, obtain tool JSON schemas, or directly initiate calls. These operations are of no difference from those described in the previous sections (MCP, OpenAPI, Hubtools).

## Example

The following example, taken from `examples/langchain_related/openai_langchain_arxiv_example.py`, shows how to combine the OpenAI client with LangChain tools:

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
        assistant_tool_messages = registry.recover_tool_call_assistant_message(
            tool_calls, tool_responses
        )
        messages.extend(assistant_tool_messages)

        # Send results back to the model for continued conversation
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=registry.get_tools_json(),
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
        tools=registry.get_tools_json(),
        tool_choice="auto",
    )
    print(response)
    
    # Process tool calls in a loop
    response = handle_tool_calls(response, messages)
    
    # Output final response content
    if response.choices[0].message.content:
        print(response.choices[0].message.content)
```

## Notes

- Ensure the corresponding extension dependencies (e.g., langchain) are installed.
- The `with_namespace` parameter allows flexible namespace configuration when registering tools to avoid naming conflicts from different sources.

The LangChain integration module enhances the Tool Registry's flexibility in supporting various tool sources, making it easier for developers to invoke different types of tools through a unified interface.
