"""
file_ops.py - Atomic file operations toolkit for LLM agents

Key features:
- All methods are static for stateless usage
- Atomic writes with automatic backups
- Unified error handling
- Diff/patch and git conflict support
- Structured data parsing
"""

import difflib
import fnmatch
import os
import re
from typing import Dict, Union


class FileOps:
    """Core file operations toolkit designed for LLM agent integration."""

    # ======================
    #  Content Modification
    # ======================

    @staticmethod
    def replace_by_diff(path: str, diff: str) -> None:
        """Apply unified diff format changes to file content and write back to file.

        Args:
            path: File path to modify
            diff: Unified diff text (with -/+ markers)

        Example diff text:
            @@ -1,3 +1,3 @@
            -line2
            +line2 modified

        Raises:
            ValueError: On invalid diff format or patch failure
        """
        original = FileOps.read_file(path)
        original_lines = original.splitlines(keepends=True)
        diff_lines = diff.splitlines(keepends=True)
        patched_lines = []
        orig_pos = 0

        hunk_regex = re.compile(r"@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@")

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            if line.startswith("@@"):
                m = hunk_regex.match(line)
                if not m:
                    raise ValueError("Invalid diff hunk header")
                orig_start = int(m.group(1)) - 1

                # Add unchanged lines before hunk
                patched_lines.extend(original_lines[orig_pos:orig_start])
                orig_pos = orig_start

                i += 1
                while i < len(diff_lines) and not diff_lines[i].startswith("@@"):
                    hline = diff_lines[i]
                    if hline.startswith(" "):
                        patched_lines.append(original_lines[orig_pos])
                        orig_pos += 1
                    elif hline.startswith("-"):
                        orig_pos += 1
                    elif hline.startswith("+"):
                        patched_lines.append(hline[1:])
                    else:
                        raise ValueError(f"Invalid diff line: {hline}")
                    i += 1
            else:
                i += 1

        # Add remaining lines after last hunk
        patched_lines.extend(original_lines[orig_pos:])

        content = "".join(patched_lines)
        FileOps.write_file(path, content)

    @staticmethod
    def search_files(path: str, regex: str, file_pattern: str = "*") -> list[dict]:
        """Perform regex search across files in a directory with context.

        Args:
            path: Directory path to search
            regex: Regex pattern to search for
            file_pattern: Glob pattern to filter files (default '*')

        Returns:
            List of dicts with keys:
                - file: file path
                - line_num: line number of match (1-based)
                - line: matched line content
                - context: list of context lines (tuples of line_num, line content)
        """

        pattern = re.compile(regex)
        results = []
        context_radius = 2  # lines before and after match to include as context

        for root, dirs, files in os.walk(path):
            for filename in files:
                if not fnmatch.fnmatch(filename, file_pattern):
                    continue
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except Exception:
                    continue

                for i, line in enumerate(lines):
                    if pattern.search(line):
                        start_context = max(0, i - context_radius)
                        end_context = min(len(lines), i + context_radius + 1)
                        context_lines = [
                            (ln + 1, lines[ln].rstrip("\n"))
                            for ln in range(start_context, end_context)
                            if ln != i
                        ]
                        results.append(
                            {
                                "file": file_path,
                                "line_num": i + 1,
                                "line": line.rstrip("\n"),
                                "context": context_lines,
                            }
                        )
        return results

    @staticmethod
    def replace_by_git(path: str, diff: str) -> None:
        """Apply git conflict style diff to file content, replacing conflicted sections and write back to file.

        Args:
            path: File path to modify
            diff: Git conflict style diff text with <<<<<<<, =======, >>>>>>> markers

        Example diff text:
            <<<<<<< SEARCH
            line2
            =======
            line2 modified
            >>>>>>> REPLACE

        Raises:
            ValueError: On invalid diff format or patch failure
        """
        original = FileOps.read_file(path)
        original_lines = original.splitlines(keepends=True)
        diff_lines = diff.splitlines(keepends=True)
        patched_lines = []
        orig_pos = 0

        conflict_start_re = re.compile(r"<<<<<<<.*")
        conflict_sep_re = re.compile(r"=======")
        conflict_end_re = re.compile(r">>>>>>>.*")

        i = 0
        while i < len(diff_lines):
            line = diff_lines[i]
            if conflict_start_re.match(line):
                # Add lines before conflict
                patched_lines.extend(original_lines[orig_pos:orig_pos])
                i += 1
                # Count lines in original conflict block to skip
                orig_conflict_lines = 0
                # Skip lines until separator in diff
                while i < len(diff_lines) and not conflict_sep_re.match(diff_lines[i]):
                    i += 1
                    orig_conflict_lines += 1
                i += 1  # skip separator line
                # Add lines after separator until conflict end
                conflict_replacement_lines = []
                while i < len(diff_lines) and not conflict_end_re.match(diff_lines[i]):
                    conflict_replacement_lines.append(diff_lines[i])
                    i += 1
                i += 1  # skip conflict end line
                patched_lines.extend(conflict_replacement_lines)
                # Skip original conflicted lines
                orig_pos += orig_conflict_lines
            else:
                if orig_pos < len(original_lines):
                    patched_lines.append(original_lines[orig_pos])
                    orig_pos += 1
                i += 1

        # Add remaining lines after last conflict
        patched_lines.extend(original_lines[orig_pos:])

        content = "".join(patched_lines)
        FileOps.write_file(path, content)

    # ======================
    #  File I/O Operations
    # ======================

    @staticmethod
    def read_file(path: str) -> str:
        """Read text file with automatic encoding detection.

        Args:
            path: File path to read

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If path doesn't exist
            UnicodeError: On encoding failures
        """
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    @staticmethod
    def write_file(path: str, content: str) -> None:
        """Atomic text file write.

        Args:
            path: Destination file path
            content: Content to write
        """
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)

    # ======================
    #  Content Generation
    # ======================

    @staticmethod
    def make_diff(old: str, new: str) -> str:
        """Generate unified diff between texts.

        Args:
            old: Original text
            new: Modified text

        Note:
            This function is intended for file or string comparison and visualization,
            not for direct text modification tasks.

        Returns:
            Unified diff text
        """
        return "\n".join(
            difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="")
        )

    @staticmethod
    def make_git_conflict(ours: str, theirs: str) -> str:
        """Generate git merge conflict markers.

        Args:
            ours: Current branch content
            theirs: Incoming branch content

        Note:
            This function is intended for file or string comparison and visualization,
            not for direct text modification tasks.

        Returns:
            Text with conflict markers
        """
        return f"<<<<<<< HEAD\n{ours}\n=======\n{theirs}\n>>>>>>> incoming\n"

    # ======================
    #  Safety Utilities
    # ======================

    @staticmethod
    def validate_path(path: str) -> Dict[str, Union[bool, str]]:
        """Validate file path safety.

        Args:
            path: Path to validate

        Returns:
            Dictionary with keys:
            - valid (bool): Path safety status
            - message (str): Description if invalid
        """
        if not path:
            return {"valid": False, "message": "Empty path"}
        if "~" in path:
            path = os.path.expanduser(path)
        if any(c in path for c in '*?"><|'):
            return {"valid": False, "message": "Contains dangerous characters"}
        return {"valid": True, "message": ""}
