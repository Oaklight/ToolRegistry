# Example Makde and Use of Calculator MCP Tool

The file [concurrent_raw_results.txt](concurrent_raw_results.txt) contains the raw statistics from the concurrent tool calls benchmark when developing different integrations of toolregistry.

We ask LLM to compute the average of metrics from this file and report back with the results.

## Example MCP Math Server

First let's define a simple FastMCP server that provides some basic math operations.

```python
"""Math server using the `fastmcp` standalone library directly.

This module implements a math server that directly uses the fastmcp
standalone library without any additional dependencies.
"""

import argparse

from fastmcp import FastMCP

# Common server configuration
server_name = "Math Server"
mcp = FastMCP(server_name)


# Register all math tools
@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b


@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract two numbers"""
    return a - b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b


@mcp.tool()
def divide(a: float, b: float) -> float:
    """Divide two numbers"""
    return a / b


# Register all math resources
@mcp.resource("math://constants/pi")
def get_pi() -> float:
    """Get the value of pi"""
    return 3.141592653589793


@mcp.resource("math://constants/e")
def get_e() -> float:
    """Get the value of e"""
    return 2.718281828459045


if __name__ == "__main__":
    """Create a unified math server with all tools and resources"""
    parser = argparse.ArgumentParser(description="Math Server")
    parser.add_argument(
        "--mode",
        type=str,
        default="stdio",
        choices=["stdio", "sse"],
        help="Server transport mode: stdio, sse, ws or http",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port number for network modes"
    )
    args = parser.parse_args()

    # Create appropriate app based on mode
    if args.mode == "stdio":
        mcp.run()
    elif args.mode == "sse":
        mcp.run(
            transport="sse",
            host="localhost",
            port=args.port,
        )
```

To run the server, we can use one of the following commands:

```bash
python math_server.py --mode stdio
python math_server.py --mode sse --port 8000
```

Note, the current recommended network transport is streamable HTTP instead of SSE.

## How to Register and Use It

We will implement using Cicada `MultiModalModel` and OpenAI client to show case different ways to integrate with the tool registry.

### Cicada `MultiModalModel` example

```python
import json
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry

load_dotenv()
PORT = os.getenv("PORT", 8000)

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

input_file = "examples/hub_related/concurrent_raw_results.txt"

with open(input_file) as f:
    input_content = f.read()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--mode", default="stdio", choices=["stdio", "sse"], help="Mode of transport"
    )
    args = parser.parse_args()

    if args.mode == "sse":
        # SSE
        transport = f"http://localhost:{PORT}/sse"
    else:
        # stdio
        transport = "/home/pding/projects/toolregistry/examples/mcp_related/mcp_servers/math_server.py"

    tool_registry.register_from_mcp(transport, with_namespace=True)

    print(tool_registry.get_available_tools())

    # Example instruction to compute the averages
    instruction = f"""
    I have a few test results from multiple runs. Please use the available tools to compute the averages of the metrics for each category. 
    The input is as 
    {input_content}
    """

    # Query LLM to get result
    response = llm.query(instruction, tools=tool_registry, stream=stream)
    cprint(json.dumps(response, indent=2))
```

### OpenAI client example

```python
import argparse
import os

from dotenv import load_dotenv
from openai import OpenAI

from toolregistry import ToolRegistry

# Load environment variables from .env file
load_dotenv()
PORT = os.getenv("PORT", 8000)

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

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
        "content": f"""
    I have a few test results from multiple runs. Please use the available tools to compute the averages of the metrics for each category. 
    The input is as {input_content}""",
    }
]
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument(
        "--mode", default="stdio", choices=["stdio", "sse"], help="Mode of transport"
    )
    args = parser.parse_args()

    if args.mode == "sse":
        # SSE
        transport = f"http://localhost:{PORT}/sse"
    else:
        # stdio
        transport = "/home/pding/projects/toolregistry/examples/mcp_related/mcp_servers/math_server.py"

    tool_registry.register_from_mcp(transport, with_namespace=True)

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

```
