import inspect
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec

# Load environment variables from .env file
load_dotenv()


model_name = os.getenv("MODEL", "deepseek-v3")
API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")
OPENAPI_SERVER_URL = os.getenv("OPENAPI_SERVER_URL", "http://localhost:8000")
OPENAPI_BEARER_TOKENS = os.getenv("OPENAPI_BEARER_TOKENS", None)
stream = os.getenv("STREAM", "True").lower() == "true"

# Initialize tool registry and register Calculator static methods
tool_registry = ToolRegistry()

input_file = "examples/hub_related/concurrent_raw_results.txt"

with open(input_file) as f:
    input_content = f.read()


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
        "content": inspect.cleandoc(f"""
    I have a few test results from multiple runs. Please use the available tools to compute the averages of the metrics for each category. 
    The input is as {input_content}"""),
    }
]
if __name__ == "__main__":
    base_url = OPENAPI_SERVER_URL
    client_config = HttpxClientConfig(
        base_url=base_url,
        headers={"Authorization": f"Bearer {OPENAPI_BEARER_TOKENS}"}
        if OPENAPI_BEARER_TOKENS
        else None,
        timeout=10.0,
    )
    openapi_spec = load_openapi_spec(base_url)

    tool_registry.register_from_openapi(
        client_config, openapi_spec, with_namespace=True
    )

    print(tool_registry.get_available_tools())

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
