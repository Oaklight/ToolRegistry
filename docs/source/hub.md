# Hub Tools and Static Method Integration

## Purpose of Hub

Hub encapsulates commonly used tools as static methods (@staticmethod) in classes, serving as ready-to-use tool groups. This design offers several advantages:

1. **Organization**: Related tool methods are grouped in the same class for easier management and maintenance
2. **Reusability**: Pre-built tools can be imported and used directly without reimplementation
3. **Consistency**: All tools follow the same interface specification
4. **Extensibility**: New tool classes or methods can be easily added

## Currently Available Hub Tools

For latest list of predefined tools, please check out [**latest available**](https://github.com/Oaklight/ToolRegistry/tree/master/src/toolregistry/hub)

1. **Calculator** - Mathematical calculation tools

   The Calculator provides a comprehensive set of mathematical functions, including but not limited to:

   - Constants: pi, e, tau, inf, nan
   - Basic arithmetic: addition (add), subtraction (subtract), multiplication (multiply), division (divide), modulo (mod)
   - Powers and roots: power, square root (sqrt), cube root (cbrt), integer square root (isqrt)
   - Distance and norms: Euclidean distance (dist), Euclidean norm (hypot)
   - Trigonometric functions: sin, cos, tan, asin, acos, atan, degrees, radians
   - Hyperbolic functions: sinh, cosh, tanh, asinh, acosh, atanh
   - Logarithmic and exponential functions: log, ln, log10, log2, log1p, exp, expm1
   - Numerical processing: abs, round, floor, ceil, trunc, copysign, frexp, ldexp, modf, remainder, nextafter, ulp, fmod, isclose
   - Combinatorics: factorial, gcd, lcm, comb, perm
   - Special functions: erf, erfc, gamma, lgamma
   - Numerical validation: isfinite, isinf, isnan
   - Statistical functions: average, median, mode, standard_deviation, min, max, sum, prod, fsum
   - Financial calculations: simple_interest, compound_interest
   - Random number generation: random, randint
   - Expression evaluation: evaluate, supports combined expression calculations

   Example usage:

   ```python
   from toolregistry.hub import Calculator as calc
   print(calc.add(1, 2))  # Output: 3
   print(calc.evaluate("add(2, 3) * power(2, 3) + sqrt(16)"))  # Output: 44
   ```

2. **FileOps** - Atomic file operations toolkit for LLM agents

   **Design Focus**: This class primarily handles operations related to **file content**, including reading, atomic writing (overwrite/append), content searching, and advanced modifications using diffs. It emphasizes safety and atomicity for content manipulation.

   FileOps is a collection of static methods designed to facilitate safe, atomic, and advanced file operations, especially suited for integration with large language model (LLM) agents. It provides utilities for reading, writing, and modifying file contents with built-in safety mechanisms like automatic backups.

   Key features include:

   - Atomic file writing (overwrite), creating the file if it doesn't exist, with temporary file usage for safe writes (`write_file`)
   - Appending content to a file, creating it if it doesn't exist (`append_file`)
   - Reading text files with automatic encoding detection (`read_file`)
   - Applying unified diff format changes directly to files (`replace_by_diff`)
   - Applying git conflict style diffs directly to files (`replace_by_git`)
   - Generating unified diff text for content comparison (`make_diff`)
   - Generating git conflict marker text to simulate merge conflicts (`make_git_conflict`)
   - Validating file path safety to prevent dangerous characters and path injection (`validate_path`)
   - Performing regex searches across files in a directory (`search_files`), returning matches with context lines. Parameters include `path` (directory to search), `regex` (pattern to search for), and optional `file_pattern` (glob pattern like `*.py`).

   The `replace_by_diff` and `replace_by_git` methods have been updated to accept only the file path and diff string as arguments. They apply the diff directly to the file content and write the changes back to the file atomically, without returning the modified content.

   Example usage:

   ```python
   from toolregistry.hub import FileOps as fio

   # Assume a file at /tmp/toolregistry/sample.txt with content "Hello World"

   # example of replace_by_diff
   content = fio.read_file("/tmp/toolregistry/sample.txt") # Hello World
   diff = """@@ -1 +1 @@
   -Hello World
   +Hello Universe"""
   fio.replace_by_diff("/tmp/toolregistry/sample.txt", diff)

   # example of replace_by_git
   content = fio.read_file("/tmp/toolregistry/sample.txt") # Hello Universe
   diff = """<<<<<<< SEARCH
   Hello Universe
   =======
   Hello Multiverse
   >>>>>>> REPLACE"""
   fio.replace_by_git("/tmp/toolregistry/sample.txt", diff)
   content = fio.read_file("/tmp/toolregistry/sample.txt") # Hello Multiverse

   # example of search_files
   results = fio.search_files("/path/to/search", r"important_keyword", "*.log")
   # results will be a list of dictionaries, each containing file path, line number, matched line, and context lines. For example, search for `bananas`

   # [{'context': [(1, 'The quick brown fox jumps over the lazy dog.'),
   #            (2, 'This file contains a juicy apple.'),
   #            (4, 'Another line for context.'),
   #            (5, 'Yet another sentence to make the file longer.')],
   # 'file': '/tmp/tmpi_h8_mm3/file1.txt',
   # 'line': 'bananas are yellow and sweet.',
   # 'line_num': 3}]
   ```

3. **Filesystem** - Comprehensive file system operations

   **Design Focus**: This class focuses on operations related to file system **structure, state, and basic metadata**. It deals with checking existence and types, listing contents, managing files/directories (copy/move/delete), handling paths, and retrieving basic attributes like size and modification time.

   - File/directory existence checks (`exists`, `is_file`, `is_dir`)
   - Directory listing (`list_dir`)
   - File/directory copy/move/delete (`copy`, `move`, `delete`)
   - Path manipulation (`join_paths`, `get_absolute_path`)
   - Size and modification time (`get_size`, `get_last_modified_time`)
   - Directory creation (`create_dir`)
   - Empty file creation/timestamp update (`create_file` - like `touch`)

4. **UnitConverter** - Extensive unit conversion tools
   - Temperature: Celsius, Fahrenheit, Kelvin
   - Length: meters, feet, cm, inches
   - Weight: kg, pounds
   - Time: seconds, minutes
   - Capacity: liters, gallons
   - Area: sqm, sqft
   - Speed: kmh, mph
   - Data storage: bits, bytes, KB, MB
   - Pressure: pascal, bar, atm
   - Power: watts, kW, horsepower
   - Energy: joules, calories, kWh
   - Frequency: Hz, kHz, MHz
   - Fuel economy: km/l, mpg
   - Electrical: ampere, volt, ohm
   - Magnetic: weber, tesla, gauss
   - Radiation: gray, sievert
   - Light intensity: lux, lumen

## Registering Hub Tools and Static Methods

Hub tools are registered to ToolRegistry using the `register_static_tools` method. Additionally, any static method (@staticmethod) from a Python class can be registered as a tool using the `StaticMethodIntegration` module. This allows developers to extend the functionality of ToolRegistry by creating custom tool classes with static methods.

### Registering Custom Static Methods

To register static methods from a custom class, use the `StaticMethodIntegration` module:

```python
from toolregistry import ToolRegistry

class CustomTools:
    @staticmethod
    def greet(name: str) -> str:
        return f"Hello, {name}!"

registry = ToolRegistry()
registry.register_static_tools(CustomTools)

# List registered tools
print(registry.get_available_tools())
# Output: ['greet']
```

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator

registry = ToolRegistry()
registry.register_static_tools(Calculator)  # Basic registration
```

### `with_namespace` Option

Using `with_namespace=True` parameter adds the class name as a namespace prefix to tool names:

```python
registry.register_static_tools(Calculator, with_namespace=True)
```

This will register tools with names like `Calculator.add`, `Calculator.subtract`, etc.

**Advantages of using with_namespace**:

1. Avoids naming conflicts between methods with same names in different classes
2. More clearly identifies tool source
3. Maintains naming consistency

## Example Code

```python
from toolregistry import ToolRegistry
from toolregistry.hub import Calculator, FileOps

# Create tool registry
registry = ToolRegistry()

# Register Calculator tools (with namespace)
registry.register_static_tools(Calculator, with_namespace=True)

# Register FileOps tools (without namespace)
registry.register_static_tools(FileOps)

# Get available tools list
print(registry.get_available_tools())
# Output: ['Calculator.add', 'Calculator.subtract', ..., 'read_file', 'write_file', ...]
```
