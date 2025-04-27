import json
import os
from pprint import pprint

# pip install cicada-agent
from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import WebSearchSearxng

# Load environment variables from .env file
load_dotenv()


model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")  # SearxNG实例URL

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

llm = MultiModalModel(
    api_key=API_KEY,
    api_base_url=BASE_URL,
    model_name=model_name,
    stream=stream,
)

tool_registry = ToolRegistry()

websearch_searxng = WebSearchSearxng(SEARXNG_URL)
tool_registry.register_from_class(
    websearch_searxng
)  # Register the web search tool with the registry

print(tool_registry.get_available_tools())

# Example query using the web search tool
response = llm.query(
    "Chicago weather today",
    tools=tool_registry,
    stream=llm.stream,
)

print("Search Results:")
print(response["content"])

# cprint(json.dumps(response, indent=2))
