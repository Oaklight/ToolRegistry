# Consecutive Tool Call Examples

## Cicada `MultiModalModel` Implementation

This example shows how to use ToolRegistry with the [Cicada](https://cicada.lab.oaklight.cn) `MultiModalModel`

One nice thing here is that it handles consecutive tool calls automatically.

```python
import os
from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from toolregistry import ToolRegistry

# Initialize Cicada model
model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"

llm = MultiModalModel(
    api_key="your-api-key",
    api_base_url="https://api.deepseek.com/",
    model_name=model_name,
    stream=stream,
)

# Initialize ToolRegistry
tool_registry = ToolRegistry()

# Register tools
@tool_registry.register
def get_weather(location: str):
    return f"Weather in {location}: Sunny, 25°C"

@tool_registry.register
def c_to_f(celsius: float) -> float:
    fahrenheit = (celsius * 1.8) + 32
    return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"

# Query the model with tools
response = llm.query(
    "What's the temperature of Shanghai, reply using Fahrenheit?",
    tools=tool_registry,
    stream=llm.stream,
)
print(response["content"])
cprint(json.dumps(response,indent=2))
```

response reads

```json
The current temperature in Shanghai is 77°F.
{
  "content": "The current temperature in Shanghai is 77\u00b0F.",
  "formatted_response": "[Response]: The current temperature in Shanghai is 77\u00b0F.",
  "tool_chain": [
    {
      "content": "",
      "tool_responses": {
        "call_mOnZUGqQhhmvj0lIKEUcncAn": "Weather in Shanghai: Sunny, 25\u00b0C"
      }
    },
    {
      "content": "",
      "tool_responses": {
        "call_lDQ0Nq0HRXHnmhoX6PJzmBHo": "25.0 celsius degree == 77.0 fahrenheit degree"
      }
    }
  ]
}
```

## OpenAI Client Implementation

This example demonstrates integration with OpenAI's API. As we mentioned in previous article, we shall handle consecutive tool calls manually.

```python
import os

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()
from toolregistry import ToolRegistry

# Initialize ToolRegistry
tool_registry = ToolRegistry()


# Register tools using decorator
@tool_registry.register
def get_weather(location: str):
    """Get the weather for a specific location"""
    return f"Weather in {location}: Sunny, 25°C"


@tool_registry.register
def c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit"""
    fahrenheit = (celsius * 1.8) + 32
    return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"


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
```

response reads

```python
Tool calls: [ChatCompletionMessageToolCall(id='call_qcb10odnylzts5qhae9jvt7v', function=Function(arguments='{"location":"Shanghai"}', name='get_weather'), type='function', index=0)]
location='Shanghai'
Tool calls: [ChatCompletionMessageToolCall(id='call_ew7cm09z893u57102aeny2zp', function=Function(arguments='{"celsius":25}', name='c_to_f'), type='function', index=0)]
celsius=25.0
The temperature in Shanghai is 77°F.
```
