import os

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()
from toolregistry import ToolRegistry
from toolregistry.hub import UnitConverter

# Initialize ToolRegistry
tool_registry = ToolRegistry()


# Register tools using decorator
@tool_registry.register
def get_weather(location: str):
    """Get the weather for a specific location"""
    return f"Weather in {location}: Sunny, 25°C"


# @tool_registry.register
# def c_to_f(celsius: float) -> float:
#     """Convert Celsius to Fahrenheit"""
#     fahrenheit = (celsius * 1.8) + 32
#     return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"

# replace c_to_f with hub tool UnitConverter
tool_registry.register_from_class(UnitConverter, with_namespace=True)

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
    model="deepseek-v3",
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
            model="deepseek-v3",
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
