import os
import tempfile
import unittest
from pathlib import Path
from toolregistry.hub.file_ops import FileOps


class TestFileOps(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_file = Path(self.test_dir.name) / "test.txt"
        self.test_file.write_text("line1\nline2\nline3\n")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_generate_and_apply_diff(self):
        old = ["line1", "line2", "line3"]
        new = ["line1", "line2 modified", "line3"]
        diff = FileOps.generate_diff(old, new)
        result = FileOps.apply_diff(old, diff)
        self.assertIn("line2 modified", result)
        self.assertNotIn("line2", result)

    def test_patch_file(self):
        old_content = "line1\nline2\nline3\n"
        new_content = "line1\nline2 modified\nline3\n"
        diff = FileOps.generate_diff(old_content.splitlines(), new_content.splitlines())
        FileOps.patch_file(self.test_file, diff)
        content_after = self.test_file.read_text()
        self.assertIn("line2 modified", content_after)

    def test_replace_lines(self):
        FileOps.replace_lines(self.test_file, r"line2", "line2 replaced")
        content = self.test_file.read_text()
        self.assertIn("line2 replaced", content)

    def test_insert_lines(self):
        FileOps.insert_lines(self.test_file, r"line2", ["inserted line"])
        content = self.test_file.read_text()
        self.assertIn("inserted line", content)

    def test_delete_lines(self):
        FileOps.delete_lines(self.test_file, r"line2")
        content = self.test_file.read_text()
        self.assertNotIn("line2", content)

    def test_find_and_replace(self):
        FileOps.find_and_replace(self.test_file, r"line3", "line3 replaced")
        content = self.test_file.read_text()
        self.assertIn("line3 replaced", content)

    def test_append_to_file(self):
        FileOps.append_to_file(self.test_file, "appended line")
        content = self.test_file.read_text()
        self.assertIn("appended line", content)


if __name__ == "__main__":
    unittest.main()
