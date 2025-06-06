import json
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.openapi import HttpxClientConfig, load_openapi_spec

load_dotenv()

# Initialize LLM model
model_name = os.getenv("MODEL", "deepseek-v3")
API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")
OPENAPI_SERVER_URL = os.getenv("OPENAPI_SERVER_URL", "http://localhost:8000")
OPENAPI_BEARER_TOKENS = os.getenv("OPENAPI_BEARER_TOKENS", None)
stream = os.getenv("STREAM", "True").lower() == "true"

llm = MultiModalModel(
    api_key=API_KEY,
    api_base_url=BASE_URL,
    model_name=model_name,
    stream=stream,
)

base_url = OPENAPI_SERVER_URL
client_config = HttpxClientConfig(
    base_url=base_url,
    headers={"Authorization": f"Bearer {OPENAPI_BEARER_TOKENS}"}
    if OPENAPI_BEARER_TOKENS
    else None,
    timeout=10.0,
)
openapi_spec = load_openapi_spec(base_url)

# Initialize tool registry and register Calculator static methods
tool_registry = ToolRegistry()
tool_registry.register_from_openapi(client_config, openapi_spec)
print(tool_registry.get_available_tools())

input_file = "examples/hub_related/concurrent_raw_results.txt"

with open(input_file) as f:
    input_content = f.read()

# Example instruction to compute the averages
instruction = f"""
I have a few test results from multiple runs. Please use the available tools to compute the averages of the metrics for each category. The input is as 
{input_content}
"""

# Query LLM to get result
response = llm.query(instruction, tools=tool_registry, stream=stream)
cprint(json.dumps(response, indent=2))
