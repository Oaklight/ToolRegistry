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
        results = registry.execute_tool_calls(tool_calls)

        # Construct assistant messages with results
        assistant_tool_messages = registry.build_tool_call_messages(tool_calls, results)

        messages.extend(assistant_tool_messages)

        # Send the results back to the model
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=registry.get_schemas(),
            tool_choice="auto",
        )
    return response


if __name__ == "__main__":
    # Any langchain_core BaseTool works, including tools from partner packages.
    # The sunset langchain-community package is not required.
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

    print(registry.list_tools())

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
        tools=registry.get_schemas(),
        tool_choice="auto",
    )

    print(response)
    # Handle tool calls using the new function (without iteration limit)
    response = handle_tool_calls(response, messages)

    # Print final response
    if response.choices[0].message.content:
        print(response.choices[0].message.content)
