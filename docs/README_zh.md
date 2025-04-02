# 文档生成流程说明

[English](README_en)

本文档说明 API 文档的生成流程和相关工具的使用方法。

## 概述

文档系统包含：

- Sphinx 用于 API 文档自动生成
- Markdown 用于手动编写文档
- 自动化脚本维护文档一致性

## 关键文件

### `regenerate_api_template.sh`

主脚本功能：

1. 使用`sphinx-apidoc`自动生成 API 文档
2. 通过`.docignore`排除指定文件
3. 维护模块索引

使用方法：

```bash
./regenerate_api_template.sh
```

### `.docignore`

指定文档生成时需要排除的文件/目录，格式与`.gitignore`相同。

示例：

```
tests/
examples/
*_test.py
```

### `Makefile`

包含命令：

- 生成 HTML 文档(`make html`)
- 清理生成的文件(`make clean`)

## 工作流程

1. **环境准备**：

   ```bash
   pip install -r requirements.txt
   ```

2. **生成 API 文档**：

   ```bash
   ./regenerate_api_template.sh
   ```

3. **构建文档**：

   ```bash
   make html
   ```

4. **查看文档**：
   打开`build/html/index.html`

## 手动文档

手动文档应使用 Markdown(.md)格式编写，存放于：

- `source/` - 主文档章节
- `source/api/` - API 概览和使用示例

## 维护说明

- 代码有重大变更后运行`./regenerate_api_template.sh`
- 添加测试文件或示例时更新`.docignore`
- 内容修改后重新构建文档(`make html`)

## 常见问题

常见问题：

- 模块缺失：检查`regenerate_api_template.sh`中的`MODULES`
- 排除无效：检查`.docignore`模式
- 构建失败：确认 Python/Sphinx 版本与 requirements.txt 一致
