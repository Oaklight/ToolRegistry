"""ToolRegistry Hub module providing commonly used tools.

This module serves as a central hub for various utility tools including:
- Calculator: Basic arithmetic operations
- FileSystem: File system operations
- FileOps: Advanced file manipulation functions

Example:
    >>> from toolregistry.hub import Calculator, FileSystem, FileOps
    >>> calc = Calculator()
    >>> result = calc.add(1, 2)
    >>> fs = FileSystem()
    >>> exists = fs.exists('/path/to/file')
    >>> ops = FileOps()
    >>> ops.replace_lines('file.txt', 5, 'new content')
"""

from .calculator import (
    Calculator,
    add,
    divide,
    evaluate,
    multiply,
    power,
    sqrt,
    subtract,
)
from .filesystem import (
    FileSystem,
    copy,
    create_dir,
    delete,
    exists,
    get_absolute_path,
    get_size,
    is_dir,
    is_file,
    join_paths,
    list_dir,
    move,
    read_file,
    write_file,
)

from .file_ops import (
    FileOps,
    generate_diff,
    apply_diff,
    patch_file,
    replace_lines,
    insert_lines,
    delete_lines,
    find_and_replace,
    append_to_file,
)

__all__ = [
    "Calculator",
    "add",
    "subtract",
    "multiply",
    "divide",
    "power",
    "sqrt",
    "evaluate",
    "FileSystem",
    "exists",
    "is_file",
    "is_dir",
    "list_dir",
    "read_file",
    "write_file",
    "copy",
    "move",
    "delete",
    "get_size",
    "join_paths",
    "get_absolute_path",
    "create_dir",
    "FileOps",
    "generate_diff",
    "apply_diff",
    "patch_file",
    "replace_lines",
    "insert_lines",
    "delete_lines",
    "find_and_replace",
    "append_to_file",
]
