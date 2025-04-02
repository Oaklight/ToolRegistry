# Documentation Generation Process (English Version)

[中文版](README_zh)

This document explains the workflow and tools for generating API documentation.

## Overview

The documentation system uses:

- Sphinx for API documentation generation
- Markdown for manual documentation
- Automated scripts to maintain consistency

## Key Files

### `regenerate_api_template.sh`

The main script that:

1. Automatically generates API documentation using `sphinx-apidoc`
2. Handles file exclusions via `.docignore`
3. Maintains the module index

Usage:

```bash
./regenerate_api_template.sh
```

### `.docignore`

Specifies files/directories to exclude from documentation generation.  
Format follows `.gitignore` conventions.

Example:

```
tests/
examples/
*_test.py
```

### `Makefile`

Contains commands for:

- Building HTML docs (`make html`)
- Cleaning generated files (`make clean`)

## Workflow

1. **Setup**:

   ```bash
   pip install -r requirements.txt
   ```

2. **Generate API Docs**:

   ```bash
   ./regenerate_api_template.sh
   ```

3. **Build Documentation**:

   ```bash
   make html
   ```

4. **View Documentation**:
   Open `build/html/index.html` in browser

## Manual Documentation

Manual documentation should be written in Markdown (.md) files in:

- `source/` - Main documentation sections
- `source/api/` - API overview and usage examples

## Maintenance

- Run `./regenerate_api_template.sh` after significant code changes
- Update `.docignore` when adding new test files or examples
- Rebuild documentation (`make html`) after content changes

## Troubleshooting

Common issues:

- Missing modules: Check `MODULES` in regenerate_api_template.sh
- Incorrect exclusions: Verify `.docignore` patterns
- Build failures: Check Python/Sphinx versions match requirements.txt
