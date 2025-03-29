import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# pip install cicada-agent
from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint

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

from toolregistry import ToolRegistry

tool_registry = ToolRegistry()


# register tools
@tool_registry.register
def get_weather(location: str):
    return f"Weather in {location}: Sunny, 25°C"


@tool_registry.register
def c_to_f(celsius: float) -> float:
    fahrenheit = (celsius * 1.8) + 32
    return f"{celsius} celsius degree == {fahrenheit} fahrenheit degree"


# query the model with tools
response = llm.query(
    "上海的气温如何，用华氏度回答我?",
    tools=tool_registry,
    stream=True,
)
print(response["content"])

cprint(response)
