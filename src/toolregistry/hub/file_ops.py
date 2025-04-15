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
        replace_in_file_with_blocks(path, diff_blocks): Replaces file content using SEARCH/REPLACE blocks
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
        result = []
        diff_lines = diff.splitlines()

        # Skip header lines until first hunk
        i = 0
        while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
            i += 1

        content_index = 0

        while i < len(diff_lines):
            line = diff_lines[i]
            if line.startswith("@@"):
                # Parse hunk header: @@ -start,count +start,count @@
                hunk_header = line
                import re

                m = re.match(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@", hunk_header)
                if not m:
                    i += 1
                    continue
                orig_start = int(m.group(1)) - 1  # zero-based index
                orig_len = int(m.group(2)) if m.group(2) else 1

                # Add unchanged lines before hunk
                while content_index < orig_start:
                    result.append(content[content_index])
                    content_index += 1

                i += 1
                # Process hunk lines
                while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                    diff_line = diff_lines[i]
                    if diff_line.startswith(" "):
                        # Context line, copy from original
                        result.append(content[content_index])
                        content_index += 1
                    elif diff_line.startswith("-"):
                        # Removed line, skip in original
                        content_index += 1
                    elif diff_line.startswith("+"):
                        # Added line, add to result
                        result.append(diff_line[1:])
                    i += 1
            else:
                i += 1

        # Add remaining lines after last hunk
        while content_index < len(content):
            result.append(content[content_index])
            content_index += 1

        return result

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

    @staticmethod
    def replace_in_file_with_conflict_blocks(
        path: Union[str, Path], conflict_blocks: str
    ) -> None:
        """Replaces file content using conflict-style blocks inspired by Git merge conflicts.

        The input string should contain one or more conflict blocks in the following format:
            <<<<<<< SEARCH
            [exact content to find in the file]
            =======
            [replacement content]
            >>>>>>> REPLACE

        This format is similar to Git conflict markers used during merges or rebases,
        providing an intuitive way to specify multiple precise replacements in a file.

        Args:
            path: Path to the file to modify
            conflict_blocks: String containing one or more conflict blocks as described above

        Raises:
            ValueError: If the conflict_blocks format is invalid or if any SEARCH block is not found in the file content
        """
        content = Path(path).read_text().splitlines()
        blocks = []
        lines = conflict_blocks.splitlines()
        i = 0
        while i < len(lines):
            if lines[i].strip() == "<<<<<<< SEARCH":
                i += 1
                search_lines = []
                while i < len(lines) and lines[i].strip() != "=======":
                    search_lines.append(lines[i])
                    i += 1
                if i >= len(lines) or lines[i].strip() != "=======":
                    raise ValueError("Invalid conflict_blocks format: missing =======")
                i += 1
                replace_lines = []
                while i < len(lines) and lines[i].strip() != ">>>>>>> REPLACE":
                    replace_lines.append(lines[i])
                    i += 1
                if i >= len(lines) or lines[i].strip() != ">>>>>>> REPLACE":
                    raise ValueError(
                        "Invalid conflict_blocks format: missing >>>>>>> REPLACE"
                    )
                i += 1
                blocks.append((search_lines, replace_lines))
            else:
                i += 1

        if not blocks:
            raise ValueError("No conflict blocks found in conflict_blocks")

        new_content = content[:]
        for search_lines, replace_lines in blocks:
            # Find the first occurrence of search_lines in new_content
            found = False
            for idx in range(len(new_content) - len(search_lines) + 1):
                if new_content[idx : idx + len(search_lines)] == search_lines:
                    # Replace the matched lines with replace_lines
                    new_content = (
                        new_content[:idx]
                        + replace_lines
                        + new_content[idx + len(search_lines) :]
                    )
                    found = True
                    break
            if not found:
                raise ValueError("SEARCH block not found in file content")

        diff = FileOps.generate_diff(content, new_content)
        FileOps.patch_file(path, diff)
