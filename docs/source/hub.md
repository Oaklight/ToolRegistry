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

   - Basic arithmetic: addition, subtraction, multiplication, division
   - Scientific operations: power, square root, trigonometric, logarithmic
   - Statistical functions: average, median, mode, standard deviation
   - Financial calculations: simple/compound interest
   - Random number generation
   - Expression evaluation

2. **FileOps** - Advanced file content manipulation

   - Generate and apply unified diffs
   - Patch files with diffs
   - Line-based operations: replace, insert, delete
   - Find and replace operations
   - File appending
   - File verification (hash calculation)
   - File comparison

3. **Filesystem** - Comprehensive file system operations

   - File/directory existence checks
   - File reading/writing
   - Directory listing
   - File/directory copy/move/delete
   - Path manipulation
   - Size calculations
   - Directory creation

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
