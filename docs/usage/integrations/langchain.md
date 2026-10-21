# LangChain Tool Usage Guide

???+ note "Changelog"
    New in version: 0.4.9

LangChain provides various pre-built tool wrappers, but these tools are tightly coupled with its framework. This makes them inconvenient for users who prefer to use the OpenAI client or other frameworks that natively support function calling. To address this, we provide an integration module for LangChain tools.

The LangChain integration module enables the ToolRegistry to support LangChain-based tools. With this module, you can easily register and invoke tools while benefiting from both synchronous and asynchronous calling modes, ensuring unified efficient execution across different environments.

## Usage Guide

No extra is required. The integration is structural: any object exposing `name`,
`description`, a parameter schema, and a sync and/or async runner can be
registered with `source="langchain"`. A `langchain_core.tools.BaseTool` from any
provider or partner package satisfies this out of the box.

???+ warning "`langchain-community` is sunset"
    Upstream `langchain-community` is read-only and its last release was 0.4.2
    (May 2026). ToolRegistry no longer depends on it. If you still need a
    community tool, install `langchain-community` yourself, or register the
    underlying callable as a plain Python function with `registry.register(...)`.

Schema sources are tried in this order: `input_schema`, `args_schema`, a
`parameters` JSON-schema dict, then an `args` dict; pydantic-v1 models are read
through their `schema()` method, so `required` is preserved. Runners are tried
as `_run` / `run` / `func` for sync and `_arun` / `arun` / `coroutine` for
async; a sync-only tool is served asynchronously through a worker thread, and
an async-only plain object must be called through `ainvoke()`.

1. **Setup Tool Instances**

    Use any `BaseTool` implementation (a partner package such as
    `langchain-openai`, or a custom class), or a plain object with the same
    shape. The community tool package is not needed.

2. **Register Tools**

    Use `register()` with `source="langchain"` or `register_async()` with
    `source="langchain"` to register tools. Here is an example with a custom
    tool:

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

    A plain object works too — no LangChain install required:

    ```python
    class LocalSearch:
        name = "search"
        description = "Search a local index"
        args = {"query": {"type": "string", "description": "Search query"}}

        def _run(self, query: str) -> str:
            return f"results for {query}"

    registry.register(LocalSearch(), source="langchain")
    ```

    You certainly can pass a single tool instance or a list of them.

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
    # Any langchain_core BaseTool works; langchain-community is not required.
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

## Notes

- No dependency is required for the integration. Install `langchain-core` (or a partner package) only if you build tools as `BaseTool` classes; plain objects with `name`, `description`, `args` and `_run` work as-is.
- `langchain-community` is sunset upstream and is no longer a ToolRegistry dependency.
- The `namespace` parameter allows flexible namespace configuration when registering tools to avoid naming conflicts from different sources.

The LangChain integration module enhances the Tool Registry's flexibility in supporting various tool sources, making it easier for developers to invoke different types of tools through a unified interface.
