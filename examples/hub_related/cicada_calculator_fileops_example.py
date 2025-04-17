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
Please compute the averages of the metrics for each category. Attention to the EXEC_MODE, there are two different types. Compute average metrics separately. So there should be 8 results The input is at {input_file}. Write your output to {output_file}

"""

# Query LLM to get result
response = llm.query(instruction, tools=tool_registry, stream=stream)
cprint(json.dumps(response, indent=2))
