# DateTime Utilities

The `DateTime` module provides simple and focused utilities for retrieving the current date and time in ISO 8601 format. It is designed for use in LLM function calling scenarios.

## Features

- Get the current UTC time in ISO 8601 format.
- Static methods for easy integration.

## Example Usage

```python
from toolregistry_hub import DateTime

current_time = DateTime.now()
print(current_time)
```

## Output

```bash
2025-08-11T09:10:44.926245+00:00
```
