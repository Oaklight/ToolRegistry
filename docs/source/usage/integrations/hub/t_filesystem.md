# Filesystem - Comprehensive file system operations

```{tip}
Refined in version: 0.4.3 <br>
New in version: 0.4.2
```

**Design Focus**: This class focuses on operations related to file system **structure, state, and basic metadata**. It deals with checking existence and types, listing contents, managing files/directories (copy/move/delete), handling paths, and retrieving basic attributes like size and modification time.

- File/directory existence checks (`exists`, `is_file`, `is_dir`)
- Directory listing (`list_dir`)
- File/directory copy/move/delete (`copy`, `move`, `delete`)
- Path manipulation (`join_paths`, `get_absolute_path`)
- Size and modification time (`get_size`, `get_last_modified_time`)
- Directory creation (`create_dir`)
- Empty file creation/timestamp update (`create_file` - like `touch`)
