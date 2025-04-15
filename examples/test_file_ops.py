import tempfile
import unittest
from pathlib import Path
from pprint import pprint

from toolregistry.hub.file_ops import FileOps


class TestFileOps(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_file = Path(self.test_dir.name) / "test.txt"
        self.test_file.write_text("line1\nline2\nline3\n")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_make_diff(self):
        old = "line1\nline2\nline3\n"
        new = "line1\nline2 modified\nline3\n"
        diff = FileOps.make_diff(old, new)
        self.assertIn("@@ -1,3 +1,3 @@", diff)
        self.assertIn("-line2", diff)
        self.assertIn("+line2 modified", diff)

    def test_replace_by_diff(self):
        original = "line1\nline2\nline3\n"
        self.test_file.write_text(original)
        diff = FileOps.make_diff(original, "line1\nline2 modified\nline3\n")
        FileOps.replace_by_diff(str(self.test_file), diff)
        content = self.test_file.read_text()
        self.assertIn("line2 modified", content)
        self.assertNotIn("line2\nline3\n", content)

    def test_make_git_conflict(self):
        ours = "line1\nline2\n"
        theirs = "line1\nline2 modified\n"
        conflict = FileOps.make_git_conflict(ours, theirs)
        self.assertIn("<<<<<<< HEAD", conflict)
        self.assertIn("=======", conflict)
        self.assertIn(">>>>>>> incoming", conflict)
        self.assertIn(ours.strip(), conflict)
        self.assertIn(theirs.strip(), conflict)

    def test_replace_by_git(self):
        original = "line1\nline2\nline3\n"
        self.test_file.write_text(original)
        diff = FileOps.make_git_conflict(
            "line1\nline2\nline3\n", "line1\nline2 modified\nline3\n"
        )
        FileOps.replace_by_git(str(self.test_file), diff)
        content = self.test_file.read_text()
        self.assertIn("line2 modified", content)
        self.assertNotIn("line2\nline3\n", content)

    def test_read_file(self):
        content = FileOps.read_file(str(self.test_file))
        self.assertIn("line1", content)

    def test_write_file(self):
        new_content = "new content\n"
        FileOps.write_file(str(self.test_file), new_content)
        content = self.test_file.read_text()
        self.assertEqual(content, new_content)

    def test_validate_path(self):
        valid = FileOps.validate_path("valid_path.txt")
        self.assertTrue(valid["valid"])
        invalid_chars = FileOps.validate_path("invalid|path.txt")
        self.assertFalse(invalid_chars["valid"])
        empty = FileOps.validate_path("")
        self.assertFalse(empty["valid"])

    def test_search_files(self):
        # Setup multiple test files with content
        file1 = Path(self.test_dir.name) / "file1.txt"
        file2 = Path(self.test_dir.name) / "file2.log"
        file3 = Path(self.test_dir.name) / "file3.txt"
        file1.write_text("apple\nbanana\ncherry\n")
        file2.write_text("dog\ncat\napple pie\n")
        file3.write_text("elephant\nbanana split\nfig\n")

        # Search for 'banana' in all .txt files
        results = FileOps.search_files(self.test_dir.name, r"banana", "*.txt")
        pprint(results)
        # Expect matches in file1.txt and file3.txt only
        files_found = {res["file"] for res in results}
        self.assertIn(str(file1), files_found)
        self.assertIn(str(file3), files_found)
        self.assertNotIn(str(file2), files_found)

        # Check line numbers and matched lines
        for res in results:
            self.assertIn("banana", res["line"])
            self.assertTrue(res["line_num"] > 0)
            # Context lines should not include the matched line itself
            context_lines = [line for _, line in res["context"]]
            self.assertNotIn(res["line"], context_lines)

        # Search for 'apple' in all files
        results_all = FileOps.search_files(self.test_dir.name, r"apple")
        files_found_all = {res["file"] for res in results_all}
        self.assertIn(str(file1), files_found_all)
        self.assertIn(str(file2), files_found_all)
        self.assertNotIn(str(file3), files_found_all)
