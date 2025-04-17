import json
import os
from pprint import pprint

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# pip install cicada-agent
from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint

from toolregistry import ToolRegistry
from toolregistry.hub import UnitConverter

model_name = os.getenv("MODEL", "deepseek-v3")
stream = os.getenv("STREAM", "True").lower() == "true"  # Configurable stream option

API_KEY = os.getenv("API_KEY", "your-api-key")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com/")

llm = MultiModalModel(
    api_key=API_KEY,
    api_base_url=BASE_URL,
    model_name=model_name,
    stream=stream,
)

tool_registry = ToolRegistry()

# register tools
@tool_registry.register
def get_weather(location: str):
    return f"Weather in {location}: Sunny, 25°C"

# @tool_registry.register
# def c_to_f(celsius: float) -> float:
#     fahrenheit = (celsius * 1.8) + 32
#     return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"

# replace c_to_f with hub tool UnitConverter
tool_registry.register_from_class(UnitConverter, with_namespace=True)

# query the model with tools
response = llm.query(
    "What's the temperature of Shanghai, reply using Fahrenheit?",
    tools=tool_registry,
    stream=llm.stream,
)
print(response["content"])

cprint(json.dumps(response, indent=2))
