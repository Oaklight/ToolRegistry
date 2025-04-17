import json
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

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

spec_url = "http://localhost:8000"
# Initialize tool registry and register Calculator static methods
tool_registry = ToolRegistry()
tool_registry.register_from_openapi(spec_url)
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
