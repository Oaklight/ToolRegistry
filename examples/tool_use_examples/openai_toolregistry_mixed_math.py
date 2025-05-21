import asyncio
import os
from pprint import pprint

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

# ================ register OPENAPI server (async) ================
print("================ OpenAPI ================")


async def async_register():
    await openapi_registry.register_from_openapi_async(
        openapi_spec_url, with_namespace=True
    )


OPENAPI_PORT = os.getenv(
    "OPENAPI_PORT", 8000
)  # default OPENAPI_PORT 8000, change via environment variable
openapi_registry = ToolRegistry("openapi_math")
openapi_spec_url = f"http://localhost:{OPENAPI_PORT}"
OPENAPI_PORT = os.getenv(
    "OPENAPI_PORT", 8000
)  # default OPENAPI_PORT 8000, change via environment variable
asyncio.run(async_register())
pprint(openapi_registry.get_available_tools())
pprint(openapi_registry._sub_registries)


# ================ register MCP server (sync) ================
print("================ MCP ================")
MCP_PORT = os.getenv(
    "MCP_PORT", 8000
)  # default MCP_PORT 8000, change via environment variable
mcp_registry = ToolRegistry("mcp_math")
mcp_server_url = f"http://localhost:{MCP_PORT}/sse"
mcp_registry.register_from_mcp(mcp_server_url, with_namespace=True)
pprint(mcp_registry.get_available_tools())
pprint(mcp_registry._sub_registries)

# ================ mix registry ================
print("================ MIXUP ================")
mixed_registry = openapi_registry
mixed_registry.merge(mcp_registry)
pprint(mixed_registry.get_available_tools())
pprint(mixed_registry._sub_registries)

# ================ testing ================
# Set up OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)


messages = [
    {
        "role": "user",
        "content": "I have 15 chestnuts. Joe ate 3. How many chestnuts do I have left?",
    }
]

# Make the chat completion request
response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=mixed_registry.get_tools_json(),
    tool_choice="auto",
)

# Handle tool calls using ToolRegistry
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)

    # Execute tool calls
    tool_responses = mixed_registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    # Construct assistant messages with results
    assistant_tool_messages = mixed_registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses
    )
    print(assistant_tool_messages)

    # Send the results back to the model
    messages.extend(assistant_tool_messages)
    second_response = client.chat.completions.create(
        model=model_name, messages=messages
    )

    # Print final response
    print(second_response.choices[0].message.content)
