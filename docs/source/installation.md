# Installation

## Prerequisites

Before setting up ToolRegistry, ensure you have the following installed:

- **Python 3.8+** is required for basic functionality, **Python 3.10+** is required for MCP support.
- We recommend using `conda/mamba` or `pipx` to manage isolated environments. \
  Download Conda/Mamba from: [Conda Forge](https://conda-forge.org/download/)

## Installation via pip

Basic installation (requires **Python >= 3.8**):

```bash
pip install toolregistry
```

Installation with MCP support (requires **Python >= 3.10**):

```bash
pip install toolregistry[mcp]
```

### Installation from Source

Basic installation from source (requires **Python >= 3.8**):

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install .
```

Installation from source with MCP support (requires **Python >= 3.10**):

```bash
git clone https://github.com/Oaklight/ToolRegistry.git
cd ToolRegistry
pip install .[mcp]
```
