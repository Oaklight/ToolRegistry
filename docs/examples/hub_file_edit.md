# FileOps Example: Editing a File with LLM

This example demonstrates how to use the `FileOps` tool to modify a file using instructions provided to a Large Language Model (LLM). The `FileOps` tool allows for operations such as reading, writing, and editing files.

One thing worth noting is that the `FileOps` tool can handle both `git` conflict/merge style and unified `diff` style edits. This flexibility allows you to choose the style that best fits your needs and capability of the LLM. You can direct LLM to use either style in your instructions.

Also, `FileOps` tool is implemented as a Python class with only staticmethod. In this case, you can avoid creating an instance of the class and directly register the class type to the `ToolRegistry`.

## Cicada `MultiModalModel` implementation

```python
import json
import os

from cicada.core.model import MultiModalModel
from cicada.core.utils import cprint
from dotenv import load_dotenv

from toolregistry import ToolRegistry
from toolregistry.hub import FileOps

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

# Initialize tool registry and register FileOps static methods
tool_registry = ToolRegistry()
tool_registry.register_from_class(FileOps)


test_file = "examples/hub_related/sample.txt"
# drop existing file
if os.path.exists(test_file):
    os.remove(test_file)

# Create sample file if not exists
if not os.path.exists(test_file):
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("Hello world!\nThis is a sample file.\nHave a nice day.\n")

# Example instruction to modify the file
instruction = f"Change 'Hello world!' to 'Hello, AI world!' and add a new line 'This file was modified by an LLM.' at the end. source file is at {test_file}. Use diff style edit"

# Query LLM to get the diff patch
response = llm.query(instruction, tools=tool_registry, stream=stream)
cprint(json.dumps(response, indent=2))
```
