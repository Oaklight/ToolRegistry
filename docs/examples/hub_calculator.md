# FileOps + Calculator Example: Read, Compute, and Write Back

The file [concurrent_raw_results.txt](concurrent_raw_results.txt) contains the raw statistics from the concurrent tool calls benchmark when developing different integrations of toolregistry.

Let's make use of it to test out LLM's ability to use multiple tools from the ToolRegistry-Hub. We want LLM to read the file, compute the averages of the metrics and then write the results to a new file. We will use the `Calculator` and `FileOps` tools from the ToolRegistry-Hub.

## Cicada `MultiModalModel` Implementation

```python
import json
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import Calculator, FileOps

load_dotenv()

# Initialize LLM model
model_name = os.getenv("MODEL", "deepseek-v3")
API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")
stream = os.getenv("STREAM", "True").lower() == "true"

llm = MultiModalModel(
    api_key=API_KEY,
    api_base_url=BASE_URL,
    model_name=model_name,
    stream=stream,
)

# Initialize tool registry and register Calculator static methods
tool_registry = ToolRegistry()
tool_registry.register_from_class(Calculator, with_namespace=True)
tool_registry.register_from_class(FileOps, with_namespace=True)
print(tool_registry.get_available_tools())

input_file = "examples/hub_related/concurrent_raw_results.txt"
output_file = "examples/hub_related/concurrent_average_results.txt"
# drop existing output file
if os.path.exists(output_file):
    os.remove(output_file)

# Example instruction to compute the averages
instruction = f"""
I have a few test results from multiple runs. 
Please compute the averages of the metrics for each category. Attention to the EXEC_MODE, there are two different types. Compute average metrics separately. So there should be 8 results The input is at {input_file}. Write your output to {output_file}.
"""

# Query LLM to get result
response = llm.query(instruction, tools=tool_registry, stream=stream)
cprint(json.dumps(response, indent=2))
```

## OpenAI client example

```python
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry
from toolregistry.hub import Calculator, FileOps

# Load environment variables from .env file
load_dotenv()


model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

# Initialize tool registry and register Calculator static methods
tool_registry = ToolRegistry()
tool_registry.register_from_class(Calculator, with_namespace=True)
tool_registry.register_from_class(FileOps, with_namespace=True)
print(tool_registry.get_available_tools())

input_file = "examples/hub_related/concurrent_raw_results.txt"
output_file = "examples/hub_related/concurrent_average_results.txt"
# drop existing output file
if os.path.exists(output_file):
    os.remove(output_file)

# Set up OpenAI client
client = OpenAI(
    api_key=os.getenv("API_KEY", "your-api-key"),
    base_url=os.getenv("BASE_URL", "https://api.deepseek.com/"),
)


messages = [
    {
        "role": "user",
        "content": f"""
I have a few test results from multiple runs. 
Please compute the averages of the metrics for each category. Attention to the EXEC_MODE, there are two different types. Compute average metrics separately. So there should be 8 results The input is at {input_file}. Write your output to {output_file}. Use your available tools at hand to do this.
""",
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
