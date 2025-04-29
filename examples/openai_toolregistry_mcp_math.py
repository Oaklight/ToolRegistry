import asyncio
import os
from pprint import pprint

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()


PORT = os.getenv("PORT", 8000)  # default port 8000, change via environment variable

registry = ToolRegistry()

mcp_server_url = f"http://localhost:{PORT}/sse"

# registry.register_from_mcp(mcp_server_url)
# pprint(registry)


async def async_register():
    await registry.register_from_mcp_async(mcp_server_url, with_namespace=True)
    pprint(registry)


asyncio.run(async_register())

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
    model="deepseek-v3",
    messages=messages,
    tools=registry.get_tools_json(),
    tool_choice="auto",
)

# Handle tool calls using ToolRegistry
if response.choices[0].message.tool_calls:
    tool_calls = response.choices[0].message.tool_calls
    print(tool_calls)

    # Execute tool calls
    tool_responses = registry.execute_tool_calls(tool_calls)
    print(tool_responses)

    # Construct assistant messages with results
    assistant_tool_messages = registry.recover_tool_call_assistant_message(
        tool_calls, tool_responses
    )
    print(assistant_tool_messages)

    # Send the results back to the model
    messages.extend(assistant_tool_messages)
    second_response = client.chat.completions.create(
        model="deepseek-v3", messages=messages
    )

    # Print final response
    print(second_response.choices[0].message.content)
