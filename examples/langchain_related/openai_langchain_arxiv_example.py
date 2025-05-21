import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()


model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

registry = ToolRegistry()

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
        tool_responses = registry.execute_tool_calls(tool_calls)

        # Construct assistant messages with results
        assistant_tool_messages = registry.recover_tool_call_assistant_message(
            tool_calls, tool_responses
        )

        messages.extend(assistant_tool_messages)

        # Send the results back to the model
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=registry.get_tools_json(),
            tool_choice="auto",
        )
    return response


if __name__ == "__main__":
    from langchain_community.tools import ArxivQueryRun, PubmedQueryRun

    # Example usage of PubmedQueryRun
    arxiv_tool = ArxivQueryRun()
    pubmed_tool = PubmedQueryRun()
    registry.register_from_langchain([arxiv_tool, pubmed_tool])

    print(registry.get_available_tools())

    user_input = input("what's your recent research interests? ")
    print(user_input)

    messages = [
        {
            "role": "user",
            "content": f"I'm interested in learning more about the field of {user_input}. Please find related papers on arxiv for me",
        }
    ]

    # Make the chat completion request
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        tools=registry.get_tools_json(),
        tool_choice="auto",
    )

    print(response)
    # Handle tool calls using the new function (without iteration limit)
    response = handle_tool_calls(response, messages)

    # Print final response
    if response.choices[0].message.content:
        print(response.choices[0].message.content)
