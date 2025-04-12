"""File operations module providing advanced file content manipulation.

This module contains the FileOps class and convenience functions for:
- Generating and applying unified diffs
- Patching files with diffs
- Line-based operations: replace, insert, delete
- Find and replace operations
- File appending

Example:
    >>> from toolregistry.hub import FileOps
    >>> ops = FileOps()
    >>> ops.replace_lines('file.txt', 'old', 'new')
    >>> ops.insert_lines('file.txt', 'insert after', ['new line'])
"""

import difflib
import re
from pathlib import Path
from typing import List, Union


class FileOps:
    """Provides advanced file content manipulation operations.

    Methods:
        generate_diff(old, new): Generates unified diff
        apply_diff(content, diff): Applies diff to content
        patch_file(path, diff): Patches file with diff
        replace_lines(path, search, replace): Replaces matching lines
        insert_lines(path, after, new_lines): Inserts lines after match
        delete_lines(path, pattern): Deletes matching lines
        find_and_replace(path, search, replace): Finds and replaces text
        append_to_file(path, content): Appends content to file
    """

    @staticmethod
    def generate_diff(old: List[str], new: List[str]) -> str:
        """Generates unified diff between old and new content.

        Args:
            old: Original content lines
            new: Modified content lines

        Returns:
            String containing unified diff
        """
        return "\n".join(
            difflib.unified_diff(
                old, new, fromfile="original", tofile="modified", lineterm=""
            )
        )

    @staticmethod
    def apply_diff(content: List[str], diff: str) -> List[str]:
        """Applies unified diff to content.

        Args:
            content: Original content lines
            diff: Unified diff string

        Returns:
            List of lines with diff applied
        """
        lines = content.copy()
        diff_lines = diff.splitlines()

        # Skip header lines
        i = 0
        while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
            i += 1

        # Process hunks
        for line in diff_lines[i:]:
            if line.startswith("@@"):
                continue
            elif line.startswith("+") and not line.startswith("++"):
                lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("--"):
                if line[1:] in lines:
                    lines.remove(line[1:])

        return lines

    @staticmethod
    def patch_file(path: Union[str, Path], diff: str) -> None:
        """Patches file with unified diff.

        Args:
            path: Path to file to patch
            diff: Unified diff string
        """
        content = Path(path).read_text().splitlines()
        patched = FileOps.apply_diff(content, diff)
        Path(path).write_text("\n".join(patched))

    @staticmethod
    def replace_lines(
        path: Union[str, Path], search: str, replace: str, count: int = 0
    ) -> None:
        """Replaces lines matching search pattern.

        Args:
            path: Path to file
            search: Regex pattern to search for
            replace: Replacement string
            count: Maximum number of replacements (0=all)
        """
        content = Path(path).read_text().splitlines()
        new_content = []
        replaced = 0

        for line in content:
            if (count == 0 or replaced < count) and re.search(search, line):
                new_content.append(re.sub(search, replace, line))
                replaced += 1
            else:
                new_content.append(line)

        Path(path).write_text("\n".join(new_content))

    @staticmethod
    def insert_lines(
        path: Union[str, Path], after: str, new_lines: List[str], count: int = 1
    ) -> None:
        """Inserts lines after matching pattern.

        Args:
            path: Path to file
            after: Regex pattern to search for insertion point
            new_lines: Lines to insert
            count: Maximum number of insertions (1=first match only)
        """
        content = Path(path).read_text().splitlines()
        new_content = []
        inserted = 0

        for line in content:
            new_content.append(line)
            if inserted < count and re.search(after, line):
                new_content.extend(new_lines)
                inserted += 1

        Path(path).write_text("\n".join(new_content))

    @staticmethod
    def delete_lines(path: Union[str, Path], pattern: str, count: int = 0) -> None:
        """Deletes lines matching pattern.

        Args:
            path: Path to file
            pattern: Regex pattern to match
            count: Maximum number of deletions (0=all)
        """
        content = Path(path).read_text().splitlines()
        new_content = []
        deleted = 0

        for line in content:
            if (count == 0 or deleted < count) and re.search(pattern, line):
                deleted += 1
            else:
                new_content.append(line)

        Path(path).write_text("\n".join(new_content))

    @staticmethod
    def find_and_replace(
        path: Union[str, Path], search: str, replace: str, flags: int = 0
    ) -> None:
        """Finds and replaces text in file.

        Args:
            path: Path to file
            search: Regex pattern to search for
            replace: Replacement string
            flags: Regex flags
        """
        content = Path(path).read_text()
        Path(path).write_text(re.sub(search, replace, content, flags=flags))

    @staticmethod
    def append_to_file(
        path: Union[str, Path], content: str, separator: str = "\n"
    ) -> None:
        """Appends content to file with separator.

        Args:
            path: Path to file
            content: Content to append
            separator: Line separator (defaults to newline)
        """
        existing = Path(path).read_text()
        if existing and not existing.endswith(separator):
            existing += separator
        Path(path).write_text(existing + content)

