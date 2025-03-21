#!/bin/bash

# Directory paths
SOURCE_DIR="source/api"
INDEX_FILE="source/api/index.md"
MODULES=("toolregistry")
ROOT_DIR="../src"

# Ensure the output directory exists
mkdir -p "$SOURCE_DIR"

# Regenerate API documentation for each module
for module in "${MODULES[@]}"; do
    module_dir="$ROOT_DIR/$module"
    if [[ -d "$module_dir" ]]; then
        echo "Regenerating API documentation for $module..."
        sphinx-apidoc -o "$SOURCE_DIR" "$module_dir" -f
    else
        echo "Warning: Module directory $module_dir does not exist. Skipping."
    fi
done

# remove modules.rst after above executed if exist
if [[ -f "${SOURCE_DIR}/modules.rst" ]]; then
    rm ${SOURCE_DIR}/modules.rst
fi

# Regenerate index.md with {toctree} directive
echo "Regenerating index.md..."
{
    echo "# API Documentation"
    echo ""
    echo "Welcome to the API documentation for ToolRegistry. Below is a list of available modules:"
    echo ""
    echo "\`\`\`{toctree}"
    echo ":maxdepth: 2"
    echo ":caption: Contents:"
    echo ""
} >"$INDEX_FILE"

# Add module entries to the {toctree} directive
for module in "${MODULES[@]}"; do
    module_name=$(basename "$module")
    if [[ -f "$SOURCE_DIR/${module_name}.rst" ]]; then
        echo "${module_name}" >>"$INDEX_FILE"
    fi
done

# Close the {toctree} directive
echo "\`\`\`" >>"$INDEX_FILE"

echo "API documentation and index.md regeneration complete. Files are located in $SOURCE_DIR and $INDEX_FILE."
