import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

# Load environment variables from .env file
load_dotenv()


model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

# Initialize tool registry and register Calculator static methods
tool_registry = ToolRegistry()
tool_registry.register_from_class(Calculator, with_namespace=True)

# Set up OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
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


messages = [
    {
        "role": "user",
        "content": (
            "You are tasked to examine the Calculator tool. "
            "Especially its help and evaluate method. "
            "Make sure to include a variety of operations and functions. especially those not directly exposed by the Calculator. "
        ),
    }
]
if __name__ == "__main__":
    # Make the chat completion request
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        tools=tool_registry.get_tools_json(),
        tool_choice="auto",
    )

    # Handle tool calls using the new function (without iteration limit)
    response = handle_tool_calls(response, messages)

    # Print final response
    if response.choices[0].message.content:
        print(response.choices[0].message.content)
