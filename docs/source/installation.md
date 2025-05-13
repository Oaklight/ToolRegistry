# Installation

[![PyPI version](https://badge.fury.io/py/toolregistry.svg)](https://badge.fury.io/py/toolregistry)

## Prerequisites

Before setting up ToolRegistry, ensure you have the following installed:

- **Python 3.8+** is required for basic functionality. For modules requiring higher versions, see the table below.
- We recommend using `conda/mamba` or `pipx` to manage isolated environments.  
  Download Conda/Mamba from: [Conda Forge](https://conda-forge.org/download/)

## Installation via pip

### Basic Installation

Install the core package (requires **Python >= 3.8**):

```bash
pip install toolregistry
```

### Installing with Extra Support Modules

Extra modules can be installed by specifying extras in brackets. This method accommodates additional modules as the project evolves.

For example, to install specific extra supports:
```bash
pip install toolregistry[mcp,openapi]
```

Below is a table summarizing available extra modules:

| Extra Module | Python Requirement | Example Command                   |
|--------------|--------------------|-----------------------------------|
| mcp          | Python >= 3.10     | pip install toolregistry[mcp]     |
| openapi      | Python >= 3.8      | pip install toolregistry[openapi] |

### Installation from Source

#### Basic Installation from Source

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install .
```

#### Installing from Source with Extra Support Modules

Clone the repository and install the package with desired extras. For instance, to install both MCP and OpenAPI supports:

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install .[mcp,openapi]
