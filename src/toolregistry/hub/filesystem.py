"""File system operations module providing file and directory utilities.

This module contains the FileSystem class and convenience functions for:
- File and directory existence checks
- File reading/writing
- Directory listing
- File/directory copy/move/delete
- Path manipulation

Example:
    >>> from toolregistry.hub import FileSystem
    >>> fs = FileSystem()
    >>> fs.create_dir('new_dir')
    # Note: create_file is part of FileSystem, write_file is in FileOps
    >>> fs.create_file('new_dir/file.txt', 'content')
    >>> fs.list_dir('new_dir')
    ['file.txt']
"""

import shutil
import time
from pathlib import Path
from typing import List, Union


class FileSystem:
    """Provides file system operations related to structure, state, and metadata.

    Methods:
        exists(path): Checks if path exists
        is_file(path): Checks if path is a file
        is_dir(path): Checks if path is a directory
        list_dir(path): Lists directory contents
        create_file(path, content): Creates file with content (Consider using FileOps.write_file for atomicity)
        copy(src, dst): Copies file/directory
        move(src, dst): Moves/renames file/directory
        delete(path): Deletes file/directory
        get_size(path): Gets file/directory size in bytes
        get_last_modified_time(path): Gets file last modified time (Unix timestamp)
        join_paths(*paths): Joins path components
        get_absolute_path(path): Gets absolute path
        create_dir(path): Creates directory
    """

    @staticmethod
    def exists(path: Union[str, Path]) -> bool:
        """Checks if path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        return Path(path).exists()

    @staticmethod
    def is_file(path: Union[str, Path]) -> bool:
        """Checks if path is a file.

        Args:
            path: Path to check

        Returns:
            True if path is a file, False otherwise
        """
        return Path(path).is_file()

    @staticmethod
    def is_dir(path: Union[str, Path]) -> bool:
        """Checks if path is a directory.

        Args:
            path: Path to check

        Returns:
            True if path is a directory, False otherwise
        """
        return Path(path).is_dir()

    @staticmethod
    def list_dir(
        path: Union[str, Path], depth: int = 1, show_hidden: bool = False
    ) -> List[str]:
        """Lists contents of directory up to a specified depth.

        Args:
            path: Directory path
            depth: Maximum depth to list contents (default is 1, meaning immediate children).
                   A depth of 2 includes children and grandchildren, etc.
                   Depth must be >= 1.
            show_hidden: Whether to include hidden files/directories (those starting with '.')
                         (default is False).

        Returns:
            List of relative paths of items in the directory up to the specified depth.

        Raises:
            ValueError: If depth is less than 1.
            FileNotFoundError: If the path does not exist or is not a directory.
        """
        base_path = Path(path)
        if not base_path.is_dir():
            raise FileNotFoundError(
                f"Path is not a directory or does not exist: {path}"
            )
        if depth < 1:
            raise ValueError("Depth must be 1 or greater.")

        if depth == 1:
            # For depth 1, return only the names of immediate children
            items = base_path.iterdir()
            if not show_hidden:
                items = (p for p in items if not p.name.startswith("."))
            return [p.name for p in items]
        else:
            # For depth > 1, use rglob and filter by depth, returning relative paths
            results = []
            for p in base_path.rglob("*"):
                try:
                    relative_path = p.relative_to(base_path)
                    # The number of parts in the relative path corresponds to the depth level
                    # e.g., 'file.txt' has 1 part (depth 1)
                    # 'subdir/file.txt' has 2 parts (depth 2)
                    if len(relative_path.parts) <= depth:
                        # Check if any part of the relative path starts with '.' if show_hidden is False
                        is_hidden = any(
                            part.startswith(".") for part in relative_path.parts
                        )
                        if show_hidden or not is_hidden:
                            results.append(str(relative_path))
                except ValueError:
                    # This can happen under certain conditions, e.g., symlink loops
                    # or permission issues during traversal. We'll skip such entries.
                    # Consider adding logging here if more detailed diagnostics are needed.
                    continue
                except PermissionError:
                    # Skip entries we don't have permission to access
                    continue
            return results

    @staticmethod
    def create_file(path: Union[str, Path], content: str = "") -> None:
        """Creates file with optional content.

        Note: This is a simple write operation. For atomic writes, consider using
              `FileOps.write_file` from the `file_ops` module.

        Args:
            path: File path to create
            content: Optional content to write (defaults to empty string)
        """
        Path(path).write_text(content, encoding="utf-8")  # Specify encoding

    @staticmethod
    def copy(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """Copies file or directory.

        Args:
            src: Source path
            dst: Destination path
        """
        src_path = Path(src)
        dst_path = Path(dst)

        if src_path.is_file():
            shutil.copy2(src_path, dst_path)
        elif src_path.is_dir():  # Check if it's a directory before copying
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)  # Allow overwriting
        else:
            raise FileNotFoundError(f"Source path is not a file or directory: {src}")

    @staticmethod
    def move(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """Moves/renames file or directory.

        Args:
            src: Source path
            dst: Destination path
        """
        src_path = Path(src)
        dst_path = Path(dst)
        # Use shutil.move for better cross-filesystem compatibility
        shutil.move(str(src_path), str(dst_path))

    @staticmethod
    def delete(path: Union[str, Path]) -> None:
        """Deletes file or directory recursively.

        Args:
            path: Path to delete
        """
        path_obj = Path(path)
        if path_obj.is_file():
            path_obj.unlink()
        elif path_obj.is_dir():
            shutil.rmtree(path_obj)
        # If it doesn't exist or is something else (like a broken symlink), do nothing or raise?
        # Current behavior: Fails silently if path doesn't exist or isn't file/dir after checks.

    @staticmethod
    def get_size(path: Union[str, Path]) -> int:
        """Gets file/directory size in bytes. For directories, sums file sizes recursively.

        Args:
            path: Path to check size of

        Returns:
            Size in bytes

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if path_obj.is_file():
            return path_obj.stat().st_size
        elif path_obj.is_dir():
            return sum(f.stat().st_size for f in path_obj.rglob("*") if f.is_file())
        else:
            # Handle other path types like symlinks if necessary, or raise error
            return 0  # Or raise an error for unsupported types

    @staticmethod
    def get_last_modified_time(path: Union[str, Path]) -> float:
        """Gets the last modified time of a file or directory.

        Args:
            path: Path to the file or directory.

        Returns:
            The last modified time as a Unix timestamp (float).

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        path_obj = Path(path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        return path_obj.stat().st_mtime

    @staticmethod
    def join_paths(*paths: Union[str, Path]) -> str:
        """Joins path components into a normalized string path.

        Args:
            *paths: Path components to join

        Returns:
            Joined and normalized path as a string.
        """
        # Using os.path.join for better compatibility if mixing Path and str
        # and returning a string as often expected by other os functions.
        return str(Path(*paths))

    @staticmethod
    def get_absolute_path(path: Union[str, Path]) -> str:
        """Gets absolute path as a normalized string.

        Args:
            path: Path to convert

        Returns:
            Absolute path as a string.
        """
        return str(Path(path).absolute())

    @staticmethod
    def create_dir(
        path: Union[str, Path], parents: bool = True, exist_ok: bool = True
    ) -> None:
        """Creates directory, including parent directories if needed.

        Defaults allow creating nested directories and don't raise error if it exists.

        Args:
            path: Directory path to create
            parents: Create parent directories if needed (defaults to True)
            exist_ok: Don't raise error if directory exists (defaults to True)
        """
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)
