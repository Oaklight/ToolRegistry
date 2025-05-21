# FileOps - Atomic file operations toolkit for LLM agents

```{note}
New in version: 0.4.2
```

**Design Focus**: This class primarily handles operations related to **file content**, including reading, atomic writing (overwrite/append), content searching, and advanced modifications using diffs. It emphasizes safety and atomicity for content manipulation.

FileOps is a collection of static methods designed to facilitate safe, atomic, and advanced file operations, especially suited for integration with large language model (LLM) agents. It provides utilities for reading, writing, and modifying file contents with built-in safety mechanisms like automatic backups.

Key features include:

- Atomic file writing (overwrite), creating the file if it doesn't exist, with temporary file usage for safe writes (`write_file`)
- Appending content to a file, creating it if it doesn't exist (`append_file`)
- Reading text files with automatic encoding detection (`read_file`)
- Applying unified diff format changes directly to files (`replace_by_diff`)
- Applying git conflict style diffs directly to files (`replace_by_git`)
- Generating unified diff text for content comparison (`make_diff`)
- Generating git conflict marker text to simulate merge conflicts (`make_git_conflict`)
- Validating file path safety to prevent dangerous characters and path injection (`validate_path`)
- Performing regex searches across files in a directory (`search_files`), returning matches with context lines. Parameters include `path` (directory to search), `regex` (pattern to search for), and optional `file_pattern` (glob pattern like `*.py`).

The `replace_by_diff` and `replace_by_git` methods have been updated to accept only the file path and diff string as arguments. They apply the diff directly to the file content and write the changes back to the file atomically, without returning the modified content.

Example usage:

```python
from toolregistry.hub import FileOps as fio

# Assume a file at /tmp/toolregistry/sample.txt with content "Hello World"

# example of replace_by_diff
content = fio.read_file("/tmp/toolregistry/sample.txt") # Hello World
diff = """@@ -1 +1 @@
-Hello World
+Hello Universe"""
fio.replace_by_diff("/tmp/toolregistry/sample.txt", diff)

# example of replace_by_git
content = fio.read_file("/tmp/toolregistry/sample.txt") # Hello Universe
diff = """<<<<<<< SEARCH
Hello Universe
=======
Hello Multiverse
>>>>>>> REPLACE"""
fio.replace_by_git("/tmp/toolregistry/sample.txt", diff)
content = fio.read_file("/tmp/toolregistry/sample.txt") # Hello Multiverse

# example of search_files
results = fio.search_files("/path/to/search", r"important_keyword", "*.log")
# results will be a list of dictionaries, each containing file path, line number, matched line, and context lines. For example, search for `bananas`
```

```json
[{"context": [(1, "The quick brown fox jumps over the lazy dog."),
           (2, "This file contains a juicy apple."),
           (4, "Another line for context."),
           (5, "Yet another sentence to make the file longer.")],
"file": "/tmp/tmpi_h8_mm3/file1.txt",
"line": "bananas are yellow and sweet.",
"line_num": 3}]
```
