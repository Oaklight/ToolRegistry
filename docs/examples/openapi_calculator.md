# 创建和使用 Calculator OpenAPI 工具示例

本示例演示了如何：

1. 使用 FastAPI 创建一个简单的计算器 API。该 API 提供加、减、乘、除等基本算术运算。
2. 将此 API 服务作为 `ToolRegistry` 工具供 LLM 使用，计算文件中各指标的平均值。

我们将复用之前计算器示例中的文件 [concurrent_raw_results.txt](concurrent_raw_results.txt)。

## 步骤一：创建计算器 API

首先定义一个简单的 FastAPI 服务器，提供基本的数学运算。

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

可以使用以下命令运行服务：

```bash
uvicorn openapi_calculator:app --reload --host 0.0.0.0 --port 8000
```

或

```bash
python openapi_calculator.py
```

## 步骤二：注册和使用 OpenAPI 工具

!!! note "API 变更"
    此前，`register_from_openapi` 需要 `spec_url` 和可选的 `base_url` 参数，设计上追求简洁。但在实践中，我们发现 HTTP 请求需要更多定制化能力，例如许多 OpenAPI 服务需要认证头或自定义超时。因此我们做了以下调整：

    `register_from_openapi` 方法现在需要两个参数：

    - `client_config`：使用 `toolregistry.openapi.HttpxClientConfig` 对象配置 HTTP 客户端（headers、auth、timeout 等），提供更大的灵活性。
    - `openapi_spec`：使用 `load_openapi_spec` 或 `load_openapi_spec_async` 等函数从文件路径或服务/规范的 URL 加载的 OpenAPI 规范，类型为 `Dict[str, Any]`。

我们分别使用 Cicada `MultiModalModel` 和 OpenAI 客户端来展示与工具注册表集成的不同方式。

示例：

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

## Cicada `MultiModalModel` 示例

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

## OpenAI 客户端示例

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
