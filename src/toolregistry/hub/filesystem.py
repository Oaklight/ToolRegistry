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
    >>> fs.write_file('new_dir/file.txt', 'content')
    >>> fs.list_dir('new_dir')
    ['file.txt']
"""

import shutil
from pathlib import Path
from typing import List, Union


class FileSystem:
    """Provides file system operations.

    Methods:
        exists(path): Checks if path exists
        is_file(path): Checks if path is a file
        is_dir(path): Checks if path is a directory
        list_dir(path): Lists directory contents
        create_file(path, content): Creates file with content
        read_file(path): Reads file content
        copy(src, dst): Copies file/directory
        move(src, dst): Moves/renames file/directory
        delete(path): Deletes file/directory
        get_size(path): Gets file/directory size
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
    def list_dir(path: Union[str, Path]) -> List[str]:
        """Lists contents of directory.

        Args:
            path: Directory path

        Returns:
            List of item names in directory
        """
        return [p.name for p in Path(path).iterdir()]

    @staticmethod
    def create_file(path: Union[str, Path], content: str = "") -> None:
        """Creates file with optional content.

        Args:
            path: File path to create
            content: Optional content to write (defaults to empty string)
        """
        Path(path).write_text(content)

    @staticmethod
    def read_file(path: Union[str, Path]) -> str:
        """Reads file content.

        Args:
            path: File path to read

        Returns:
            File content as string
        """
        return Path(path).read_text()

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
        else:
            shutil.copytree(src_path, dst_path)

    @staticmethod
    def move(src: Union[str, Path], dst: Union[str, Path]) -> None:
        """Moves/renames file or directory.

        Args:
            src: Source path
            dst: Destination path
        """
        Path(src).rename(dst)

    @staticmethod
    def delete(path: Union[str, Path]) -> None:
        """Deletes file or directory.

        Args:
            path: Path to delete
        """
        path_obj = Path(path)
        if path_obj.is_file():
            path_obj.unlink()
        else:
            shutil.rmtree(path_obj)

    @staticmethod
    def get_size(path: Union[str, Path]) -> int:
        """Gets file/directory size in bytes.

        Args:
            path: Path to check size of

        Returns:
            Size in bytes
        """
        path_obj = Path(path)
        if path_obj.is_file():
            return path_obj.stat().st_size
        return sum(f.stat().st_size for f in path_obj.rglob("*") if f.is_file())

    @staticmethod
    def join_paths(*paths: Union[str, Path]) -> Path:
        """Joins path components.

        Args:
            *paths: Path components to join

        Returns:
            Joined Path object
        """
        return Path(*paths)

    @staticmethod
    def get_absolute_path(path: Union[str, Path]) -> Path:
        """Gets absolute path.

        Args:
            path: Path to convert

        Returns:
            Absolute Path object
        """
        return Path(path).absolute()

    @staticmethod
    def create_dir(
        path: Union[str, Path], parents: bool = False, exist_ok: bool = False
    ) -> None:
        """Creates directory.

        Args:
            path: Directory path to create
            parents: Create parent directories if needed (defaults to False)
            exist_ok: Don't raise error if directory exists (defaults to False)
        """
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)

