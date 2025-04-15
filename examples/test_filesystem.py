import os
import tempfile
import unittest
from pathlib import Path
from toolregistry.hub.filesystem import FileSystem
import shutil


class TestFileSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.test_dir.name) / "test_dir"
        self.dir_path.mkdir()
        self.file_path = self.dir_path / "test_file.txt"
        self.file_path.write_text("test content")

    def tearDown(self):
        self.test_dir.cleanup()

    def test_exists_is_file_is_dir(self):
        self.assertTrue(FileSystem.exists(self.file_path))
        self.assertTrue(FileSystem.is_file(self.file_path))
        self.assertFalse(FileSystem.is_dir(self.file_path))
        self.assertTrue(FileSystem.exists(self.dir_path))
        self.assertFalse(FileSystem.is_file(self.dir_path))
        self.assertTrue(FileSystem.is_dir(self.dir_path))

    def test_list_dir(self):
        contents = FileSystem.list_dir(self.dir_path)
        self.assertIn("test_file.txt", contents)

    def test_create_and_read_file(self):
        new_file = self.dir_path / "new_file.txt"
        FileSystem.create_file(new_file, "hello")
        content = FileSystem.read_file(new_file)
        self.assertEqual(content, "hello")

    def test_copy_file_and_dir(self):
        copy_file = self.dir_path / "copy_file.txt"
        FileSystem.copy(self.file_path, copy_file)
        self.assertTrue(copy_file.exists())
        copy_dir = Path(self.test_dir.name) / "copy_dir"
        FileSystem.copy(self.dir_path, copy_dir)
        self.assertTrue(copy_dir.exists())
        self.assertTrue((copy_dir / "test_file.txt").exists())

    def test_move_file_and_dir(self):
        move_file = self.dir_path / "move_file.txt"
        shutil.copy2(self.file_path, move_file)
        new_file_path = self.dir_path / "moved_file.txt"
        FileSystem.move(move_file, new_file_path)
        self.assertFalse(move_file.exists())
        self.assertTrue(new_file_path.exists())

        move_dir = Path(self.test_dir.name) / "move_dir"
        shutil.copytree(self.dir_path, move_dir)
        new_dir_path = Path(self.test_dir.name) / "moved_dir"
        FileSystem.move(move_dir, new_dir_path)
        self.assertFalse(move_dir.exists())
        self.assertTrue(new_dir_path.exists())

    def test_delete_file_and_dir(self):
        temp_file = self.dir_path / "temp_file.txt"
        temp_file.write_text("temp")
        FileSystem.delete(temp_file)
        self.assertFalse(temp_file.exists())

        temp_dir = Path(self.test_dir.name) / "temp_dir"
        temp_dir.mkdir()
        FileSystem.delete(temp_dir)
        self.assertFalse(temp_dir.exists())

    def test_get_size(self):
        size = FileSystem.get_size(self.file_path)
        self.assertGreater(size, 0)
        size_dir = FileSystem.get_size(self.dir_path)
        self.assertGreater(size_dir, 0)

    def test_join_paths_and_get_absolute_path(self):
        joined = FileSystem.join_paths(self.dir_path, "joined.txt")
        self.assertEqual(str(joined), str(self.dir_path / "joined.txt"))
        absolute = FileSystem.get_absolute_path(self.dir_path)
        self.assertTrue(absolute.is_absolute())

    def test_create_dir(self):
        new_dir = Path(self.test_dir.name) / "new_dir"
        FileSystem.create_dir(new_dir)
        self.assertTrue(new_dir.exists())
        # Test parents and exist_ok
        nested_dir = Path(self.test_dir.name) / "nested/dir"
        FileSystem.create_dir(nested_dir, parents=True, exist_ok=True)
        self.assertTrue(nested_dir.exists())


if __name__ == "__main__":
    unittest.main()
