# Installation

This guide provides detailed instructions for installing ToolRegistry with different feature sets.

## Basic Installation

Install ToolRegistry using pip:

```bash
pip install toolregistry
```

This installs the core functionality needed for basic tool registration and execution.

## Installation with Optional Dependencies

ToolRegistry supports various integrations that require additional dependencies. You can install these using the following commands:

### MCP Support

For Model Context Protocol (MCP) integration:

```bash
pip install toolregistry[mcp]
```

### OpenAPI Support

For OpenAPI/Swagger integration:

```bash
pip install toolregistry[openapi]
```

### LangChain Support

For LangChain tool integration:

```bash
pip install toolregistry[langchain]
```

### All Features

To install all optional dependencies:

```bash
pip install toolregistry[all]
```

## Development Installation

If you want to contribute to ToolRegistry or need the latest development version:

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install -e .[all]
```

## Verification

To verify your installation, run:

```python
import toolregistry
print(toolregistry.__version__)
```

## Requirements

- Python 3.8 or higher
- Operating System: Windows, macOS, or Linux

## Troubleshooting

### Common Issues

**Import Error**: If you encounter import errors, ensure you have installed the correct optional dependencies for the features you're trying to use.

**Version Conflicts**: If you experience dependency conflicts, consider using a virtual environment:

```bash
python -m venv toolregistry-env
source toolregistry-env/bin/activate  # On Windows: toolregistry-env\Scripts\activate
pip install toolregistry[all]
```

### Getting Help

If you encounter issues during installation:

1. Check the [GitHub Issues](https://github.com/Oaklight/ToolRegistry/issues)
2. Create a new issue with your system information and error details
3. Join our community discussions