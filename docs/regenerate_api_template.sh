#!/bin/bash
#
# API Documentation Auto-generation Script
# API文档自动生成脚本
#
# Features/功能:
# 1. Auto-generate Python module API docs using sphinx-apidoc
#    使用sphinx-apidoc自动生成Python模块的API文档
# 2. Support specifying ignored files/directories via .docignore
#    支持通过.docignore文件指定要忽略的文件/目录
# 3. Auto-generate module index
#    自动生成模块索引文件
#
# Usage/使用说明:
# 1. Run in docs folder of project root
#    在项目根目录的docs文件夹下运行
# 2. Add ignore patterns in .docignore (similar to .gitignore syntax)
#    在.docignore中添加要忽略的文件/目录模式(类似.gitignore语法)
# 3. Generated docs will be in source/api after running
#    运行脚本后会在source/api生成文档文件

# Documentation output directory/文档输出目录
SOURCE_DIR="source/api"
# Module index file path/模块索引文件路径
INDEX_FILE="source/api/index.md"

# Module list to generate docs (can add multiple)/要生成文档的模块列表(可添加多个模块)
MODULES=("toolregistry")

# Source code root directory (relative to script location)/源代码根目录(相对于脚本位置)
ROOT_DIR="../src"

# Ensure the output directory exists
mkdir -p "$SOURCE_DIR"

# Regenerate API References for each module
for module in "${MODULES[@]}"; do
    module_dir="$ROOT_DIR/$module"
    if [[ -d "$module_dir" ]]; then
        echo "Regenerating API References for $module..."
        sphinx-apidoc -o "$SOURCE_DIR" "$module_dir" -f -e --module-first --remove-old
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
    echo "# API References"
    echo ""
    echo "Welcome to the API references for the project. Below is a list of available modules:"
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

echo "API References and index.md regeneration complete. Files are located in $SOURCE_DIR and $INDEX_FILE."
