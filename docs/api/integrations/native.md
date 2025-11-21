# Native Integration

This section documents the native Python class integration capabilities of the ToolRegistry library.

## Architecture Overview

The Native integration enables direct registration of Python class methods as tools within the ToolRegistry framework. This integration provides a seamless way to convert existing Python classes into callable tools:

### Core Components

1. **ClassToolIntegration**: The main integration class that handles class method registration

   - Automatically detects static vs instance methods
   - Handles class instantiation when needed
   - Manages namespace assignment for organized tool hierarchy

2. **Method Registration Logic**: Intelligent registration that adapts to different class patterns
   - Static methods are registered directly from the class
   - Instance methods trigger automatic class instantiation
   - Mixed method types are handled with appropriate error messages

### Design Philosophy

- **Zero Configuration**: Minimal setup required to register Python classes
- **Intelligent Detection**: Automatic detection of method types and instantiation needs
- **Namespace Management**: Automatic namespace generation based on class names
- **Error Transparency**: Clear error messages for common integration issues

### Key Features

- **Automatic Method Discovery**: Scans classes for public callable methods
- **Smart Instantiation**: Handles both static and instance method registration
- **Namespace Support**: Automatic namespace generation from class names
- **Error Handling**: Clear error messages for problematic class structures
- **Async Support**: Full compatibility with async/await patterns
- **Reflection-Based**: Uses Python's introspection capabilities for method discovery

### Registration Patterns

#### Static Method Classes

```python
class Calculator:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b
```

Methods are registered directly without instantiation.

#### Instance Method Classes

```python
class FileManager:
    def __init__(self, base_path: str):
        self.base_path = base_path

    def read_file(self, filename: str) -> str:
        # Implementation
```

Class is automatically instantiated and instance methods are registered.

#### Mixed Method Classes

```python
class MixedClass:
    @staticmethod
    def static_method():
        pass

    def instance_method(self):
        pass
```

Automatically detected and handled appropriately.

## API Reference

### ClassToolIntegration

Handles integration with Python classes for method registration.

::: toolregistry.native.integration.ClassToolIntegration
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

## Module Overview

### Native Module

The main native integration module.

::: toolregistry.native
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true

### Native Utils

Utility functions for native integration.

::: toolregistry.native.utils
options:
show_source: false
show_root_heading: true
show_root_toc_entry: false
merge_init_into_class: true
