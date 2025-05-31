import argparse
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import WebSearchGoogle, WebSearchSearXNG

# Load environment variables from .env file
load_dotenv()

parser = argparse.ArgumentParser(description="Cicada WebSearch SearXNG Example")
parser.add_argument(
    "--query", type=str, default="Chicago weather today", help="Search query"
)
parser.add_argument(
    "--engine",
    "-e",
    choices=["google", "searxng"],
    default="google",
    help="Search engine to use",
)

args = parser.parse_args()

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")  # SearXNG实例URL

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")


llm = MultiModalModel(
    api_key=API_KEY,
    api_base_url=BASE_URL,
    model_name=model_name,
    stream=stream,
)

tool_registry = ToolRegistry()

if args.engine == "searxng":
    websearch = WebSearchSearXNG(SEARXNG_URL)
    cprint(f"Using SearXNG search engine at {SEARXNG_URL}")
else:
    websearch = WebSearchGoogle()  # Assuming there's a WebSearchGoogle class


tool_registry.register_from_class(
    websearch
)  # Register the web search tool with the registry

print(tool_registry.get_available_tools())

# Example query using the web search tool
response = llm.query(
    args.query,
    tools=tool_registry,
    stream=llm.stream,
)

print("Search Results:")
print(response["content"])

# cprint(json.dumps(response, indent=2))
