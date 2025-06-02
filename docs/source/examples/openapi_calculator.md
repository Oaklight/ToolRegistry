# Example Make and Use of Calculator OpenAPI Tool

This example demonstrates how to:

1. Create a simple calculator API using FastAPI. The API provides basic arithmetic operations such as addition, subtraction, multiplication, and division.
2. Use this API service as a `ToolRegistry` tool for LLMs to compute the average of metrics from a file.

We will reuse the file from previous calculator examples, [concurrent_raw_results.txt](concurrent_raw_results.txt).

## Step 1: Create the Calculator API

First, let's define a simple FastAPI server that provides basic math operations.

```python
from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="OpenAPI Calculator",
    description="Provides OpenAPI calculator service for addition, subtraction, multiplication, and division.",
    version="1.0.0",
)


@app.get("/add", summary="Addition")
def add(a: float, b: float):
    """
    Calculate a + b and return the result.

    Args:
        a (float): The first operand.
        b (float): The second operand.

    Returns:
        dict: A dictionary containing the key "result" with the sum of a and b.
    """
    return a + b


@app.get("/subtract", summary="Subtraction")
def subtract(a: float, b: float):
    """
    Calculate a - b and return the result.

    Args:
        a (float): The first operand.
        b (float): The second operand.

    Returns:
        dict: A dictionary containing the key "result" with the difference of a and b.
    """
    return a - b


@app.get("/multiply", summary="Multiplication")
def multiply(a: float, b: float):
    """
    Calculate a * b and return the result.

    Args:
        a (float): The first operand.
        b (float): The second operand.

    Returns:
        dict: A dictionary containing the key "result" with the product of a and b.
    """
    return a * b


@app.get("/divide", summary="Division")
def divide(a: float, b: float):
    """
    Calculate a / b and return the result.

    Args:
        a (float): The numerator.
        b (float): The denominator.

    Returns:
        dict: A dictionary containing the key "result" with the quotient of a and b.

    Raises:
        HTTPException: If b is zero.
    """
    if b == 0:
        raise HTTPException(status_code=400, detail="Divisor cannot be zero")
    return a / b


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

To run the service, you can use the following command:

```bash
uvicorn openapi_calculator:app --reload --host 0.0.0.0 --port 8000
```

or

```bash
python openapi_calculator.py
```

## Step 2: Register and Use the OpenAPI Tool

```{note}
### Updated Registration Method (As of 0.4.12)

Previously, `register_from_openapi` requires `spec_url` and optional `base_url`. It was designed to be simple. Yet in practice, we found the need for customization in HTTP requests, for example many OpenAPI services requires authentication headers or custom timeouts. Thus we made the following changes:

The `register_from_openapi` method new requires two parameters:

- `client_config`: Configures the HTTP client (headers, auth, timeout, etc.) using a `toolregistry.openapi.HttpxClientConfig` object, allowing greater flexibility.
- `openapi_spec`: The OpenAPI specification loaded as `Dict[str, Any]` using functions like `load_openapi_spec` or `load_openapi_spec_async` from a file path or URL to the service or specification.
```

We implement using both Cicada `MultiModalModel` and OpenAI client to showcase different ways to integrate with the tool registry.

Example:

```python
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec

client_config = HttpxClientConfig(base_url="http://localhost:8000")
openapi_spec = load_openapi_spec("./openapi_spec.json") # specification at local path
openapi_spec = load_openapi_spec("http://localhost:8000") # URL to service root
openapi_spec = load_openapi_spec("http://localhost:8000/openapi.json") # URL to specification

registry.register_from_openapi(
    client_config=client_config,
    openapi_spec=openapi_spec,
    with_namespace=False,
)
```

## Cicada `MultiModalModel` Example

```python
import json
import os
from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec
from toolregistry import ToolRegistry

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

# Initialize tool registry
tool_registry = ToolRegistry()

client_config = HttpxClientConfig(base_url="http://localhost:8000")
openapi_spec = load_openapi_spec("http://localhost:8000")
tool_registry.register_from_openapi(client_config, openapi_spec)

print(tool_registry.get_available_tools())

# Read input file
input_file = "examples/hub_related/concurrent_raw_results.txt"

with open(input_file) as f:
    input_content = f.read()

instruction = f"""
I have a few test results from multiple runs. Please use the available tools to compute the averages of the metrics for each category. 
The input is as {input_content}
"""

# Query LLM and fetch result
response = llm.query(instruction, tools=tool_registry, stream=stream)
cprint(json.dumps(response, indent=2))
```

## OpenAI Client Example

```python
import inspect
import os
from dotenv import load_dotenv
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec
from toolregistry import ToolRegistry
from openai import OpenAI

load_dotenv()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

# Initialize tool registry
tool_registry = ToolRegistry()

client_config = HttpxClientConfig(base_url="http://localhost:8000")
openapi_spec = load_openapi_spec("http://localhost:8000")
tool_registry.register_from_openapi(client_config, openapi_spec)

print(tool_registry.get_available_tools())

# Read input file
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
