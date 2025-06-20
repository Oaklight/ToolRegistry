import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

registry = ToolRegistry()


@registry.register
def add(a: float, b: float) -> float:
    """Add two numbers together."""
    return a + b


@registry.register
def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first."""
    return a - b


print(json.dumps(registry.get_tools_json(api_format="openai-response"), indent=2))

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
response = client.responses.create(
    model=model_name,
    input=messages,
    tools=registry.get_tools_json(api_format="openai-response"),
    tool_choice="auto",
)

tool_calls = []
for each in response.output:
    if each.type == "function_call":
        tool_calls.append(each)
print(tool_calls)

# Execute tool calls
tool_responses = registry.execute_tool_calls(tool_calls)
print(tool_responses)

# Construct assistant messages with results
assistant_tool_messages = registry.recover_tool_call_assistant_message(
    tool_calls, tool_responses, api_format="openai-response"
)
print(json.dumps(assistant_tool_messages, indent=2))

messages.extend(assistant_tool_messages)

# Send the results back to the model
response = client.responses.create(
    model=model_name,
    input=messages,
    tools=registry.get_tools_json(api_format="openai-response"),
    tool_choice="auto",
)

# Print final response
if response.output:
    print(response.output_text)
