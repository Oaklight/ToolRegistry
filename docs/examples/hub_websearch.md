# WebSearch + UnitConverter 示例：网络查询信息并转换单位

本示例演示了如何使用 ToolRegistry-Hub 中的 `WebSearch` 工具查询网络信息。我们将使用 `WebSearch` 工具搜索特定主题的信息，然后处理搜索结果。

在本示例中，我们将搜索上海的温度，然后使用 `UnitConverter` 工具将温度从摄氏度转换为华氏度。

## Cicada `MultiModalModel` 示例

```python
import argparse
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import WebSearchGoogle, WebSearchSearXNG

# Load environment variables from .env file
load_dotenv()

parser = argparse.ArgumentParser(description="Cicada WebSearch SearXNG Example")
parser.add_argument(
    "--query", type=str, default="Chicago weather today", help="Search query"
)
parser.add_argument(
    "--engine",
    "-e",
    choices=["google", "searxng"],
    default="google",
    help="Search engine to use",
)

args = parser.parse_args()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")  # SearXNG实例URL

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")


llm = MultiModalModel(
    api_key=API_KEY,
    api_base_url=BASE_URL,
    model_name=model_name,
    stream=stream,
)

tool_registry = ToolRegistry()

if args.engine == "searxng":
    websearch = WebSearchSearXNG(SEARXNG_URL)
    cprint(f"Using SearXNG search engine at {SEARXNG_URL}")
else:
    websearch = WebSearchGoogle()  # Assuming there's a WebSearchGoogle class


tool_registry.register_from_class(
    websearch
)  # Register the web search tool with the registry

print(tool_registry.get_available_tools())

# Example query using the web search tool
response = llm.query(
    args.query,
    tools=tool_registry,
    stream=llm.stream,
)

print("Search Results:")
print(response["content"])

cprint(json.dumps(response, indent=2))
```

## OpenAI 客户端示例

```python
import argparse
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry
from toolregistry.hub import UnitConverter, WebSearchGoogle, WebSearchSearXNG

# Load environment variables from .env file
load_dotenv()

parser = argparse.ArgumentParser(description="Cicada WebSearch SearXNG Example")
parser.add_argument(
    "--query", type=str, default="Chicago weather today", help="Search query"
)
parser.add_argument(
    "--engine",
    "-e",
    choices=["google", "searxng"],
    default="google",
    help="Search engine to use",
)

args = parser.parse_args()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")  # SearXNG实例URL

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")


tool_registry = ToolRegistry()

if args.engine == "searxng":
    websearch = WebSearchSearXNG(SEARXNG_URL)
    print(f"Using SearXNG search engine at {SEARXNG_URL}")
else:
    websearch = WebSearchGoogle()  # Assuming there's a WebSearchGoogle class


tool_registry.register_from_class(websearch, with_namespace=True)
tool_registry.register_from_class(UnitConverter, with_namespace=True)

print(tool_registry.get_available_tools())

# Set up OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)


messages = [
    {
        "role": "user",
        "content": "What's the temperature of Shanghai, reply using Fahrenheit?",
    }
]
# Make the chat completion request
response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=tool_registry.get_tools_json(),
    tool_choice="auto",
)


def handle_tool_calls(response, messages):
    """Handle tool calls in a loop until no more tool calls are needed"""
    while response.choices[0].message.tool_calls:
        tool_calls = response.choices[0].message.tool_calls
        print("Tool calls:", tool_calls)

        # Execute tool calls
        tool_responses = tool_registry.execute_tool_calls(tool_calls)

        # Construct assistant messages with results
        assistant_tool_messages = tool_registry.recover_tool_call_assistant_message(
            tool_calls, tool_responses
        )

        messages.extend(assistant_tool_messages)

        # Send the results back to the model
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tool_registry.get_tools_json(),
            tool_choice="auto",
        )
    return response


# Handle tool calls using the new function (without iteration limit)
response = handle_tool_calls(response, messages)

# Print final response
if response.choices[0].message.content:
    print(response.choices[0].message.content)
```
