import os
import stat
import tempfile
import unittest
from pathlib import Path
from toolregistry.hub import FileSystem
import shutil
import platform


# Helper function to set hidden attribute on Windows
def set_hidden_attribute_windows(path_str):
    if platform.system() == "Windows":
        try:
            # Using attrib command is simpler than ctypes for this context
            os.system(f'attrib +h "{path_str}"')
            # Verify (optional, raises error if attrib failed silently)
            attrs = os.stat(path_str).st_file_attributes
            if not (attrs & stat.FILE_ATTRIBUTE_HIDDEN):
                print(
                    f"Warning: Failed to set hidden attribute on {path_str}"
                )  # Or raise
        except Exception as e:
            print(
                f"Warning: Error setting hidden attribute on {path_str}: {e}"
            )  # Non-critical for test flow


class TestFileSystem(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the test run
        self.test_dir_obj = tempfile.TemporaryDirectory()
        self.test_dir_base = self.test_dir_obj.name

        # Main test directory path (as Path and str)
        self.dir_path_obj = Path(self.test_dir_base) / "test_dir"
        self.dir_path_str = str(self.dir_path_obj)
        self.dir_path_obj.mkdir()

        # Test file path (as Path and str)
        self.file_path_obj = self.dir_path_obj / "test_file.txt"
        self.file_path_str = str(self.file_path_obj)
        self.file_path_obj.write_text("test content")

        # Create items for list_dir tests
        self.subdir_obj = self.dir_path_obj / "subdir"
        self.subdir_str = str(self.subdir_obj)
        self.subdir_obj.mkdir()
        (self.subdir_obj / "nested_file.txt").write_text("nested")

        # Hidden file (dot prefix)
        self.hidden_dot_file_obj = self.dir_path_obj / ".hidden_file"
        self.hidden_dot_file_str = str(self.hidden_dot_file_obj)
        self.hidden_dot_file_obj.write_text("hidden dot")

        # Hidden dir (dot prefix)
        self.hidden_dot_dir_obj = self.dir_path_obj / ".hidden_dir"
        self.hidden_dot_dir_str = str(self.hidden_dot_dir_obj)
        self.hidden_dot_dir_obj.mkdir()
        (self.hidden_dot_dir_obj / "inside_hidden.txt").write_text("inside hidden")

        # File to be marked hidden on Windows
        self.win_hidden_file_obj = self.dir_path_obj / "win_hidden_file.txt"
        self.win_hidden_file_str = str(self.win_hidden_file_obj)
        self.win_hidden_file_obj.write_text("win hidden")
        set_hidden_attribute_windows(self.win_hidden_file_str)

    def tearDown(self):
        # Cleanup the temporary directory
        self.test_dir_obj.cleanup()

    def test_exists_is_file_is_dir(self):
        # Test with string paths
        self.assertTrue(FileSystem.exists(self.file_path_str))
        self.assertTrue(FileSystem.is_file(self.file_path_str))
        self.assertFalse(FileSystem.is_dir(self.file_path_str))
        self.assertTrue(FileSystem.exists(self.dir_path_str))
        self.assertFalse(FileSystem.is_file(self.dir_path_str))
        self.assertTrue(FileSystem.is_dir(self.dir_path_str))
        self.assertFalse(FileSystem.exists("non_existent_path"))

    def test_list_dir_depth_1(self):
        # Default: show_hidden=False, depth=1
        contents = FileSystem.list_dir(self.dir_path_str)
        self.assertIn("test_file.txt", contents)
        self.assertIn("subdir", contents)
        self.assertNotIn(".hidden_file", contents)
        self.assertNotIn(".hidden_dir", contents)
        if platform.system() == "Windows":
            # Check if the file marked with hidden attribute is filtered out
            self.assertNotIn("win_hidden_file.txt", contents)
        else:
            # On non-windows, the file without dot prefix should be listed
            self.assertIn("win_hidden_file.txt", contents)

        # show_hidden=True, depth=1
        contents_hidden = FileSystem.list_dir(self.dir_path_str, show_hidden=True)
        self.assertIn("test_file.txt", contents_hidden)
        self.assertIn("subdir", contents_hidden)
        self.assertIn(".hidden_file", contents_hidden)
        self.assertIn(".hidden_dir", contents_hidden)
        self.assertIn(
            "win_hidden_file.txt", contents_hidden
        )  # Should always be shown when show_hidden=True

    def test_list_dir_depth_2(self):
        # show_hidden=False, depth=2
        contents = FileSystem.list_dir(self.dir_path_str, depth=2)
        self.assertIn("test_file.txt", contents)
        self.assertIn("subdir", contents)
        self.assertIn(os.path.join("subdir", "nested_file.txt"), contents)
        self.assertNotIn(".hidden_file", contents)
        self.assertNotIn(".hidden_dir", contents)
        self.assertNotIn(os.path.join(".hidden_dir", "inside_hidden.txt"), contents)
        if platform.system() == "Windows":
            self.assertNotIn("win_hidden_file.txt", contents)
        else:
            self.assertIn("win_hidden_file.txt", contents)

        # show_hidden=True, depth=2
        contents_hidden = FileSystem.list_dir(
            self.dir_path_str, depth=2, show_hidden=True
        )
        self.assertIn("test_file.txt", contents_hidden)
        self.assertIn("subdir", contents_hidden)
        self.assertIn(os.path.join("subdir", "nested_file.txt"), contents_hidden)
        self.assertIn(".hidden_file", contents_hidden)
        self.assertIn(".hidden_dir", contents_hidden)
        self.assertIn(os.path.join(".hidden_dir", "inside_hidden.txt"), contents_hidden)
        self.assertIn("win_hidden_file.txt", contents_hidden)

    def test_list_dir_errors(self):
        with self.assertRaises(FileNotFoundError):
            FileSystem.list_dir("non_existent_dir")
        with self.assertRaises(ValueError):
            FileSystem.list_dir(self.dir_path_str, depth=0)

    def test_create_file_touch(self):
        # Test creating a new empty file
        new_file_str = os.path.join(self.dir_path_str, "newly_created.txt")
        self.assertFalse(os.path.exists(new_file_str))
        FileSystem.create_file(new_file_str)
        self.assertTrue(os.path.exists(new_file_str))
        self.assertEqual(os.path.getsize(new_file_str), 0)

        # Test updating timestamp of existing file (touch behavior)
        initial_mtime = os.path.getmtime(self.file_path_str)
        # Ensure enough time passes for mtime to potentially change
        import time

        time.sleep(0.01)
        FileSystem.create_file(self.file_path_str)
        final_mtime = os.path.getmtime(self.file_path_str)
        # Note: Some filesystems have low mtime resolution, so >= is safer
        self.assertGreaterEqual(final_mtime, initial_mtime)

    def test_copy_file_and_dir(self):
        copy_file_str = os.path.join(self.dir_path_str, "copy_file.txt")
        FileSystem.copy(self.file_path_str, copy_file_str)
        self.assertTrue(os.path.exists(copy_file_str))
        self.assertEqual(
            os.path.getsize(copy_file_str), os.path.getsize(self.file_path_str)
        )

        copy_dir_str = os.path.join(self.test_dir_base, "copy_dir")
        FileSystem.copy(self.dir_path_str, copy_dir_str)
        self.assertTrue(os.path.isdir(copy_dir_str))
        self.assertTrue(os.path.exists(os.path.join(copy_dir_str, "test_file.txt")))
        self.assertTrue(
            os.path.exists(os.path.join(copy_dir_str, "subdir", "nested_file.txt"))
        )

    def test_move_file_and_dir(self):
        # Move file
        move_src_file_str = os.path.join(self.dir_path_str, "move_src_file.txt")
        shutil.copy2(self.file_path_str, move_src_file_str)  # Create a file to move
        move_dst_file_str = os.path.join(self.dir_path_str, "moved_file.txt")
        FileSystem.move(move_src_file_str, move_dst_file_str)
        self.assertFalse(os.path.exists(move_src_file_str))
        self.assertTrue(os.path.exists(move_dst_file_str))

        # Move directory
        move_src_dir_str = os.path.join(self.test_dir_base, "move_src_dir")
        shutil.copytree(self.dir_path_str, move_src_dir_str)  # Create a dir to move
        move_dst_dir_str = os.path.join(self.test_dir_base, "moved_dir")
        FileSystem.move(move_src_dir_str, move_dst_dir_str)
        self.assertFalse(os.path.exists(move_src_dir_str))
        self.assertTrue(os.path.isdir(move_dst_dir_str))
        self.assertTrue(os.path.exists(os.path.join(move_dst_dir_str, "test_file.txt")))

    def test_delete_file_and_dir(self):
        # Delete file
        temp_file_str = os.path.join(self.dir_path_str, "temp_file.txt")
        Path(temp_file_str).write_text("temp")  # Create file to delete
        self.assertTrue(os.path.exists(temp_file_str))
        FileSystem.delete(temp_file_str)
        self.assertFalse(os.path.exists(temp_file_str))

        # Delete directory
        temp_dir_str = os.path.join(self.test_dir_base, "temp_dir")
        os.makedirs(temp_dir_str)  # Create dir to delete
        self.assertTrue(os.path.isdir(temp_dir_str))
        FileSystem.delete(temp_dir_str)
        self.assertFalse(os.path.exists(temp_dir_str))

    def test_get_size(self):
        size = FileSystem.get_size(self.file_path_str)
        self.assertEqual(size, len("test content"))

        # Calculate expected directory size manually
        expected_dir_size = (
            len("test content")
            + len("nested")
            + len("hidden dot")
            + len("inside hidden")
            + len("win hidden")
        )
        size_dir = FileSystem.get_size(self.dir_path_str)
        self.assertEqual(size_dir, expected_dir_size)

    def test_get_last_modified_time(self):
        mtime = FileSystem.get_last_modified_time(self.file_path_str)
        self.assertIsInstance(mtime, float)
        self.assertGreater(mtime, 0)

    def test_join_paths_and_get_absolute_path(self):
        # Test join_paths
        joined_str = FileSystem.join_paths(self.dir_path_str, "subdir", "joined.txt")
        expected_str = os.path.normpath(
            os.path.join(self.dir_path_str, "subdir", "joined.txt")
        )
        self.assertEqual(joined_str, expected_str)

        # Test get_absolute_path
        absolute_str = FileSystem.get_absolute_path(self.file_path_str)
        self.assertTrue(os.path.isabs(absolute_str))
        # Check if the absolute path actually points to the file
        self.assertTrue(
            absolute_str.endswith(os.path.join("test_dir", "test_file.txt"))
        )
        self.assertTrue(Path(absolute_str).exists())

    def test_create_dir(self):
        # Test creating a simple directory
        new_dir_str = os.path.join(self.test_dir_base, "new_simple_dir")
        FileSystem.create_dir(new_dir_str)
        self.assertTrue(os.path.isdir(new_dir_str))

        # Test creating nested directories (parents=True)
        nested_dir_str = os.path.join(self.test_dir_base, "nested", "deeply", "dir")
        FileSystem.create_dir(nested_dir_str)  # parents=True is default
        self.assertTrue(os.path.isdir(nested_dir_str))

        # Test exist_ok=True
        FileSystem.create_dir(new_dir_str, exist_ok=True)  # Should not raise error
        self.assertTrue(os.path.isdir(new_dir_str))

        # Test exist_ok=False (default behavior of Path.mkdir without exist_ok=True)
        # FileSystem.create_dir implicitly uses exist_ok=True, so we test Path directly
        with self.assertRaises(FileExistsError):
            Path(new_dir_str).mkdir(parents=True, exist_ok=False)


if __name__ == "__main__":
    unittest.main()
