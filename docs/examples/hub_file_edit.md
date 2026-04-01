# FileOps 示例：使用 LLM 编辑文件

本示例演示了如何使用 `FileOps` 工具，通过向大语言模型（LLM）提供指令来修改文件。`FileOps` 工具支持文件的读取、写入和编辑等操作。

值得注意的是，`FileOps` 工具同时支持 `git` 冲突/合并风格和统一 `diff` 风格的编辑。这种灵活性允许你根据需求和 LLM 的能力选择最合适的风格。你可以在指令中指定 LLM 使用哪种风格。

此外，`FileOps` 工具以 Python 类的形式实现，仅包含静态方法。因此你无需创建类的实例，可以直接将类类型注册到 `ToolRegistry` 中。

## Cicada `MultiModalModel` 实现

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
