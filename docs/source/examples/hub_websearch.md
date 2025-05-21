# WebSearch + UnitConverter Example: Querying the Web for Information then Converting Units

This example demonstrates how to use the `WebSearch` tool from the ToolRegistry-Hub to query the web for information. We will use the `WebSearch` tool to search for information about a specific topic and then process the results.

In this example, we will search for the temperature of Shanghai and then convert the temperature from Celsius to Fahrenheit using the `UnitConverter` tool.

## Cicada `MultiModalModel` example

```python
import argparse
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import WebSearchGoogle, WebSearchSearxng

# Load environment variables from .env file
load_dotenv()

parser = argparse.ArgumentParser(description="Cicada WebSearch SearxNG Example")
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
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")  # SearxNG实例URL

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
    websearch = WebSearchSearxng(SEARXNG_URL)
    cprint(f"Using SearxNG search engine at {SEARXNG_URL}")
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

## OpenAI client example

```python
import argparse
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry
from toolregistry.hub import UnitConverter, WebSearchGoogle, WebSearchSearxng

# Load environment variables from .env file
load_dotenv()

parser = argparse.ArgumentParser(description="Cicada WebSearch SearxNG Example")
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
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")  # SearxNG实例URL

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")


tool_registry = ToolRegistry()

if args.engine == "searxng":
    websearch = WebSearchSearxng(SEARXNG_URL)
    print(f"Using SearxNG search engine at {SEARXNG_URL}")
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
