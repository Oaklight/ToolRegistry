# Hub of Tools

```{note}
**⚠️ Important Notice**: This is a **standalone package** that can be used independently. This package was separated from `toolregistry` at version `0.4.14` and shares version format for historical continuity only. `toolregistry-hub` has **no dependencies** on `toolregistry` and is completely independent and self-sufficient. It can be used on its own or as a submodule for the main `toolregistry` package.
```

A comprehensive collection of tools designed for LLM function calling, extracted from the main ToolRegistry package to provide focused utility modules.

## Installation

To install the standalone `toolregistry-hub` package, use the following command:

```bash
pip install toolregistry-hub
```

For integration with the main `toolregistry` package, you can install it as an optional dependency:

```bash
pip install toolregistry[hub]
```

```{toctree}
:maxdepth: 2

t_calculator
t_datetime_utils
t_file_ops
t_filesystem
t_think_tool
t_unit_converter
t_websearch
```
