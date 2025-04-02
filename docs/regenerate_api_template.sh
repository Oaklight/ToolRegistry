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

# Ensure output directory exists/确保输出目录存在
mkdir -p "$SOURCE_DIR"

# Get script directory/获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# .docignore file path (for specifying ignored files/dirs)/.docignore文件路径(用于指定要忽略的文件/目录)
DOCIGNORE_FILE="$SCRIPT_DIR/.docignore"

# Read ignore patterns from .docignore (skip comments and empty lines)/从.docignore读取忽略模式(跳过注释和空行)
if [[ -f "$DOCIGNORE_FILE" ]]; then
    mapfile -t ignore_patterns < <(grep -vE '^\s*($|#)' "$DOCIGNORE_FILE")
else
    ignore_patterns=()
fi

# Main loop: Generate API docs for each module/主循环：为每个模块生成API文档
for module in "${MODULES[@]}"; do
    module_dir="$ROOT_DIR/$module"

    skip=0
    # Check for pattern matches if ignore patterns exist/如果有忽略模式则检查是否匹配
    if [[ ${#ignore_patterns[@]} -gt 0 ]]; then
        for pattern in "${ignore_patterns[@]}"; do
            # Check if ignore pattern matches module path or .py files/检查忽略模式是否匹配模块路径或.py文件
            if [[ "$module_dir" == *"$pattern"* ]] ||
                [[ "$pattern" == *.py && "$module_dir" == *"${pattern%.py}"* ]]; then
                echo "Skipping API documentation for $module because it matches .docignore pattern: $pattern"
                skip=1
                break
            fi
        done
    fi

    if [[ $skip -eq 1 ]]; then
        continue
    fi

    if [[ -d "$module_dir" ]]; then
        echo "Regenerating API documentation for $module..."
        # Call sphinx-apidoc to generate docs, passing ignore patterns as exclude params/调用sphinx-apidoc生成文档，传递忽略模式作为排除参数
        if [[ ${#ignore_patterns[@]} -gt 0 ]]; then
            sphinx-apidoc -o "$SOURCE_DIR" "$module_dir" -f "${ignore_patterns[@]}"
        else
            sphinx-apidoc -o "$SOURCE_DIR" "$module_dir" -f
        fi
    else
        echo "Warning: Module directory $module_dir does not exist. Skipping."
    fi
done

# Clean up auto-generated modules.rst file (if exists)/清理自动生成的modules.rst文件(如果存在)
if [[ -f "${SOURCE_DIR}/modules.rst" ]]; then
    rm "${SOURCE_DIR}/modules.rst"
fi

# Regenerate index.md file with {toctree} directive/重新生成index.md文件，包含{toctree}指令
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

# Add entries to {toctree} directive for each module/为每个模块添加条目到{toctree}指令
# Skip files matching any pattern in .docignore/跳过匹配.docignore中任何模式的文件
for module in "${MODULES[@]}"; do
    module_name=$(basename "$module")
    rst_file="$SOURCE_DIR/${module_name}.rst"
    if [[ -f "$rst_file" ]]; then
        skip=0
        # Skip if ignore_patterns is empty
        if [[ ${#ignore_patterns[@]} -gt 0 ]]; then
            for pattern in "${ignore_patterns[@]}"; do
                # Use shell globbing for matching (pattern from .docignore is expected to be a glob)
                if [[ "$rst_file" == *"$pattern"* ]]; then
                    skip=1
                    echo "Skipping ${module_name} because it matches .docignore pattern: $pattern"
                    break
                fi
            done
        fi
        if [[ $skip -eq 0 ]]; then
            echo "${module_name}" >>"$INDEX_FILE"
        fi
    fi
done

# Close {toctree} directive/关闭{toctree}指令
echo "\`\`\`" >>"$INDEX_FILE"

echo "API documentation and index.md regeneration complete. Files are located in $SOURCE_DIR and $INDEX_FILE."
